from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from typing_extensions import List, Type

# %% the handler


def _handler_serving(
    root: Path, requested_paths: List[str]
) -> Type[SimpleHTTPRequestHandler]:
    """
    Build a handler serving a directory tree, answering a directory with a json listing.

    :param root: The directory tree to serve.
    :param requested_paths: The list every requested path is appended to.
    :return: The handler class.
    """

    class Handler(SimpleHTTPRequestHandler):
        """
        Serves files, and directories as the json listing the dataset server answers
        with.
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def do_GET(self) -> None:
            requested_paths.append(self.path)
            super().do_GET()

        def list_directory(self, path: str) -> io.BytesIO:
            listing = [
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size,
                }
                for item in sorted(Path(path).iterdir())
            ]
            body = json.dumps(listing).encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return io.BytesIO(body)

        def log_message(self, *args) -> None:
            """
            Keep the test output free of one line per request.
            """

    return Handler


# %% the server


@dataclass
class ListingFileServer:
    """
    Serves a directory tree over http on the loopback interface, answering a directory
    with a json listing of what it holds.

    This is the contract the dataset server is read through, so a test exercises the
    real request path without a network to cross or a host to reach.
    """

    root: Path
    """
    The directory tree served.
    """

    requested_paths: List[str] = field(default_factory=list)
    """
    Every path requested so far, in order, so a test can assert what was fetched and
    what a cache hit spared.
    """

    def __post_init__(self) -> None:
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), _handler_serving(self.root, self.requested_paths)
        )
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        """
        :return: The address the served tree's root is reachable at.
        """
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        """
        Stop serving and release the port.
        """
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
