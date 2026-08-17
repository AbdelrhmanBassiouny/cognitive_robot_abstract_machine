"""
HTTP endpoints of the live bridge (default port 8765).

::

    GET /info    {running, robot, objects, plan, chart, sequenceNumber,
                  partAnnotations}
    GET /state   {sequenceNumber, frames: {prefixed_joint: position},
                  base: pose, objects: {mesh_key: pose}}
    GET /objects geometry catalog (mesh served via /mesh?key=)
    GET /models  [{index, prefix, robot}] (URDF served via /model_urdf?model=,
                  mesh served via /model_mesh/<model>/<ref>.<ext> — the real
                  extension has to be the URL's own trailing characters, since the
                  frontend's URDF loader dispatches to a mesh format by regex-
                  matching it, not by any query parameter)
    GET /plan    {signature, nodes: [{id, parent, kind, label, status, derived}]}
    GET /chart   {signature, title,
                  nodes: [{id, parent, name, class_name, life_cycle, observation}],
                  edges: [{from, to, kind}]}
    GET /presets {ok, title, presets: [{text, code, scope}],
                  scopes: [{name, label, variables}], variables: [name]}
    GET /vocabulary?scope=   {ok, entries: [{name, kind, detail, module, type}]}
    GET /members?name=&scope= {ok, name, members: [{name, kind, detail}]}
    GET /replay  {ok, start, end, frames: [{at, frames, base, objects}]}
                  (start/end query parameters in seconds since the epoch)
    GET /run     {ok, title, paused, looping, restart_pending, activity, iteration}
    POST /eql    {code, scope} -> the rendered answer rows
    POST /question {text} -> the preset matching a natural-language question
                  ({ok, matched, similarity, preset} or {ok, matched, similarity,
                  reply} when nothing on offer answers it)
    POST /run    {command} -> the run state that command produced
    POST /move   queue an object move (applied on the simulation thread)

Every ``pose`` above is ``[x, y, z, qx, qy, qz, qw]``.

Handlers only ever read finished snapshot dicts — never the world (see
:mod:`cramera.live.hooks`).
"""

from __future__ import annotations

import functools
import json
import math
import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dataclasses import asdict

from typing_extensions import Any, Dict, Optional

from cramera.logging_setup import get_logger
from cramera.live.bridge import Bridge, MalformedMoveRequest, MoveRequest
from cramera.knowledge.query_vocabulary import UnknownVocabularyName
from cramera.knowledge.queryable_knowledge import QueryScope, UnknownQueryScope
from cramera.live.query import NoQuerySourceRegistered
from cramera.live.run_control import (
    NoRunControlRegistered,
    RunCommand,
    UnknownRunCommand,
)

logger = get_logger(__name__)

DEFAULT_PORT = int(os.environ.get("LIVE_VIZ_PORT", "8765"))


class BridgeRequestHandler(BaseHTTPRequestHandler):
    """
    Serves the bridge's snapshots and accepts viewer moves.
    """

    MODEL_MESH_PATH_PATTERN = re.compile(r"^/model_mesh/(\d+)/(\d+)\.[A-Za-z0-9]+$")
    """
    ``/model_mesh/<model index>/<reference index>.<extension>`` — the extension is read
    only by the frontend to pick a mesh loader; the server resolves purely from the two
    numeric indices.
    """

    def __init__(self, *args: Any, bridge: Bridge, **kwargs: Any) -> None:
        """
        Capture the bridge before delegating, since the base constructor already
        dispatches the request synchronously.

        :param args: Positional arguments forwarded to the base handler.
        :param bridge: The bridge this handler serves.
        :param kwargs: Keyword arguments forwarded to the base handler.
        """
        self.bridge = bridge
        super().__init__(*args, **kwargs)

    def _send_json(self, payload: Dict[str, Any], code: int = 200) -> None:
        """
        Send a JSON payload with the CORS headers the viewer needs.

        :param payload: The JSON-serializable payload to send.
        :param code: HTTP status code to respond with.
        """
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """
        Entry point :class:`~http.server.BaseHTTPRequestHandler` dispatches a ``GET``
        request to, found by name as ``"do_" + self.command``.
        """
        self.route_snapshot_request()

    def route_snapshot_request(self) -> None:
        """
        Route the read-only snapshot endpoints.
        """
        if self.path.startswith("/state"):
            return self._send_json(self.bridge.get_state())
        if self.path.startswith("/plan"):
            return self._send_json(self.bridge.get_plan())
        if self.path.startswith("/chart"):
            return self._send_json(self.bridge.get_chart())
        if self.path.startswith("/objects"):
            return self._send_json({"objects": self.bridge.object_catalog()})
        if self.path.startswith("/mesh"):
            return self._send_mesh()
        if self.path.startswith("/models"):
            return self._send_json({"models": self.bridge.live_models()})
        if self.path.startswith("/model_urdf"):
            return self._send_model_urdf()
        if self.path.startswith("/model_mesh"):
            return self._send_model_mesh()
        if self.path.startswith("/presets"):
            return self._send_query_presets()
        if self.path.startswith("/vocabulary"):
            return self._send_query_vocabulary()
        if self.path.startswith("/members"):
            return self._send_query_members()
        if self.path.startswith("/replay"):
            return self._send_replay_clip()
        if self.path.startswith("/run"):
            return self._send_run_control_state()
        if self.path.startswith("/info"):
            return self._send_json(self.bridge.status())
        self.send_response(404)
        self.end_headers()

    def _send_query_presets(self) -> None:
        """
        Serve the running demo's ready-made queries, or say why there are none.
        """
        try:
            payload = {
                "ok": True,
                "title": self.bridge.query_title(),
                "presets": [asdict(preset) for preset in self.bridge.query_presets()],
                "scopes": [
                    {
                        "name": scope.value,
                        "label": scope.label,
                        "variables": self.bridge.query_variables(scope),
                    }
                    for scope in self.bridge.query_scopes()
                ],
                "variables": self.bridge.query_variables(),
            }
        except NoQuerySourceRegistered as error:
            payload = {"ok": False, "error": str(error), "presets": []}
        self._send_json(payload)

    def _send_query_vocabulary(self) -> None:
        """
        Serve every name a query of the asked-for scope may use.
        """
        try:
            payload = self.bridge.query_vocabulary(self._requested_scope()).to_payload()
        except (
            NoQuerySourceRegistered,
            UnknownQueryScope,
        ) as error:
            payload = {"ok": False, "error": str(error), "entries": []}
        self._send_json(payload)

    def _send_query_members(self) -> None:
        """
        Serve the members that follow one name's dot.
        """
        name = self._query_value("name") or ""
        try:
            payload = self.bridge.query_vocabulary(
                self._requested_scope()
            ).members_payload(name)
        except (
            NoQuerySourceRegistered,
            UnknownQueryScope,
            UnknownVocabularyName,
        ) as error:
            payload = {"ok": False, "error": str(error), "members": []}
        self._send_json(payload)

    def _requested_scope(self) -> QueryScope:
        """
        The body of knowledge the request asks about, the current state by default.

        :raises UnknownQueryScope: When the request names no such body of knowledge.
        """
        return QueryScope.of_name(
            self._query_value("scope") or QueryScope.CURRENT_STATE.value
        )

    def _send_run_control_state(self) -> None:
        """
        Serve where the running demo stands, or say why nothing can be driven.
        """
        try:
            payload = {"ok": True, **self.bridge.run_control_payload()}
        except NoRunControlRegistered as error:
            payload = {"ok": False, "error": str(error)}
        self._send_json(payload)

    def _query_value(self, name: str) -> Optional[str]:
        """
        One query-string parameter's value, or None if it is absent.

        :param name: The parameter's name.
        """
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        values = query.get(name)
        return values[0] if values else None

    def _query_int(self, name: str) -> Optional[int]:
        """
        One query-string parameter's value, parsed as an int, or None if it is absent or
        not a valid int.

        :param name: The parameter's name.
        """
        value = self._query_value(name)
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    def _query_float(self, name: str) -> Optional[float]:
        """
        One query-string parameter's value, parsed as a finite float, or None if it is
        absent or not one.

        :param name: The parameter's name.
        """
        value = self._query_value(name)
        try:
            parsed = float(value) if value is not None else None
        except ValueError:
            return None
        return parsed if parsed is not None and math.isfinite(parsed) else None

    def _send_replay_clip(self) -> None:
        """
        Serve the recorded frames of one replay window, or reject an unusable window.
        """
        start = self._query_float("start")
        end = self._query_float("end")
        if start is None or end is None or end <= start:
            return self._send_json(
                {
                    "ok": False,
                    "error": "'start' and 'end' must be numbers with start < end",
                },
                code=400,
            )
        self._send_json(self.bridge.replay_clip(start, end))

    def _send_mesh(self) -> None:
        """
        Serve one object's mesh file (plain file IO, no world access).
        """
        self._send_file(self.bridge.mesh_path(self._query_value("key") or ""))

    def _send_model_urdf(self) -> None:
        """
        Serve one tracked model's URDF text, mesh references rewritten to servable URLs.
        """
        index = self._query_int("model")
        text = self.bridge.model_urdf_text(index) if index is not None else None
        if text is None:
            self.send_response(404)
            self.end_headers()
            return
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_model_mesh(self) -> None:
        """
        Serve one tracked model's mesh reference, resolved to an absolute path (plain
        file IO, no world access).
        """
        match = self.MODEL_MESH_PATH_PATTERN.match(self.path)
        path = (
            self.bridge.model_mesh_path(int(match.group(1)), int(match.group(2)))
            if match
            else None
        )
        self._send_file(path)

    def _send_file(self, path: Optional[str]) -> None:
        """
        Stream an absolute path's bytes, or 404 when it does not resolve to a file.

        :param path: The absolute path to stream, or None/empty when nothing resolved.
        """
        if not path or not Path(path).is_file():
            self.send_response(404)
            self.end_headers()
            return
        data = Path(path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        """
        Entry point :class:`~http.server.BaseHTTPRequestHandler` dispatches a ``POST``
        request to, found by name as ``"do_" + self.command``.
        """
        if self.path.startswith("/eql"):
            return self.answer_requested_query()
        if self.path.startswith("/question"):
            return self.answer_asked_question()
        if self.path.startswith("/run"):
            return self.apply_requested_run_command()
        self.queue_requested_move()

    def _posted_payload(self) -> Optional[Dict[str, Any]]:
        """
        The request's JSON body as an object, or None when it is not one.
        """
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def answer_requested_query(self) -> None:
        """
        Answer one EQL query about the running demo.

        A query is arbitrary user input, so every way it can go wrong is reported as an
        answer the panel can render rather than as a dead request.
        """
        payload = self._posted_payload()
        if payload is None:
            return self._send_json(
                {"ok": False, "error": "body must be a JSON object"}, code=400
            )
        code = (payload.get("code") or "").strip()
        if not code:
            return self._send_json({"ok": False, "error": "empty query"})
        try:
            scope = QueryScope.of_name(
                payload.get("scope") or QueryScope.CURRENT_STATE.value
            )
        except UnknownQueryScope as error:
            return self._send_json({"ok": False, "error": str(error)}, code=400)
        try:
            return self._send_json(self.bridge.run_query(code, scope).to_payload())
        except (NoQuerySourceRegistered, UnknownQueryScope) as error:
            return self._send_json({"ok": False, "error": str(error)})
        except Exception as error:
            # a SyntaxError from the query is named by its own type, like any other
            return self._send_json(
                {"ok": False, "error": "%s: %s" % (type(error).__name__, error)}
            )

    def answer_asked_question(self) -> None:
        """
        Match a natural-language question to the running demo's ready-made queries.
        """
        payload = self._posted_payload()
        if payload is None:
            return self._send_json(
                {"ok": False, "error": "body must be a JSON object"}, code=400
            )
        text = (payload.get("text") or "").strip()
        if not text:
            return self._send_json({"ok": False, "error": "empty question"})
        try:
            return self._send_json(self.bridge.match_question(text).to_payload())
        except NoQuerySourceRegistered as error:
            return self._send_json({"ok": False, "error": str(error)})

    def apply_requested_run_command(self) -> None:
        """
        Pause, resume, restart or loop the running demo, and answer with its new state.
        """
        payload = self._posted_payload()
        if payload is None:
            return self._send_json(
                {"ok": False, "error": "body must be a JSON object"}, code=400
            )
        try:
            command = RunCommand.of_name(payload.get("command") or "")
        except UnknownRunCommand as error:
            return self._send_json({"ok": False, "error": str(error)}, code=400)
        try:
            return self._send_json(
                {"ok": True, **self.bridge.apply_run_command(command)}
            )
        except NoRunControlRegistered as error:
            return self._send_json({"ok": False, "error": str(error)})

    def queue_requested_move(self) -> None:
        """
        Queue an object move requested by the viewer.

        The payload is validated here so that malformed input is rejected on the HTTP
        thread, rather than raising later inside the simulation tick.
        """
        if not self.path.startswith("/move"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            return self._send_json({"ok": False, "error": str(error)}, code=400)
        if not isinstance(payload, dict):
            return self._send_json(
                {"ok": False, "error": "body must be a JSON object"}, code=400
            )
        try:
            move = MoveRequest.from_payload(payload)
        except MalformedMoveRequest as error:
            return self._send_json({"ok": False, "error": str(error)}, code=400)
        self.bridge.queue_move(move)
        return self._send_json({"ok": True})

    def do_OPTIONS(self) -> None:
        """
        Entry point :class:`~http.server.BaseHTTPRequestHandler` dispatches an
        ``OPTIONS`` request to, found by name as ``"do_" + self.command``.
        """
        self.answer_preflight()

    def answer_preflight(self) -> None:
        """
        CORS preflight for the viewer's cross-origin POSTs.
        """
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """
        Route the per-request access log to debug (15 Hz polling is noisy).

        :param format:``printf``-style log message format.
        :param args: Values to interpolate into ``format``.
        """
        logger.debug(format, *args)


def serve(bridge: Bridge, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """
    Start an HTTP server on a daemon thread, serving ``bridge``.

    :param bridge: The bridge every request handler on this server reads and writes.
    :param port: Port to listen on (all interfaces).
    :return: The running server.
    """
    handler = functools.partial(BridgeRequestHandler, bridge=bridge)
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
