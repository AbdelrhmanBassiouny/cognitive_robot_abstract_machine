#!/usr/bin/env bash
# Runs the whole Franka Montessori demo with the cramera viewer attached to it.
#
# Starts the cramera server, waits for it to listen, then runs the demo with
# --cramera so it serves its world and its running sort from inside its own
# process. The viewer attaches to that bridge on its own, and the EQL panel's
# buttons become questions this demo answers while it sorts.
#
# The demo runs in the foreground: its log is what you see, Ctrl-C stops it, and
# the cramera server is torn down with it.
#
# Every argument other than this script's own is passed straight to the demo, so
# anything franka_montessori_demo.py accepts works here too.
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cramera_port=8711
bridge_port=8765
server_startup_timeout_seconds=30
open_browser=1
demo_arguments=()
# what a run you are watching wants, as opposed to what the headless batch runners that
# invoke the demo module directly want. Each is dropped if the caller decides either way
# about it themselves.
default_demo_arguments=(--world2 --viewer --no-rviz)

usage() {
    cat <<USAGE
Usage: $(basename "$0") [--no-browser] [demo arguments...]

Runs the cramera server and the Franka Montessori demo together, with the demo
answering the viewer's EQL queries about the sort as it runs.

  --no-browser   Don't open the viewer; just print its URL.
  -h, --help     Show this message.

Runs with --world2 --viewer --no-rviz unless you say otherwise, since this is the
way to watch a run rather than to batch one. RViz publishing is off because you are
watching through the viewer instead, and because publishing it evaluates CasADi on
the physics thread while the plan thread is planning, which segfaults the demo.

Common demo arguments (see franka_montessori_demo.py --help for all of them):

  --no-viewer         Run headless instead of opening a MuJoCo window.
  --no-world2         Use the single-table layout instead of world2's.
  --rviz              Publish TF/markers anyway, at the risk described above.
  --no-event-monitor  Skip segmind event detection. A detector tick blocks the
                      motion for ~12ms, inside a control period; the sorting
                      verdict is unaffected either way.
  --only-shape KEY    Attempt one shape only, e.g. --only-shape square_hole.
  --no-record         Keep no results, and ask for no database at all.
  --database-uri URI  Record results somewhere other than the configured database.

Examples:

  ./$(basename "$0") --only-shape square_hole
  ./$(basename "$0") --no-browser --no-viewer --only-shape square_hole

The demo records every iteration to the database named by
FRANKA_MONTESSORI_SORTING_DATABASE_URI, or to a local Postgres one when that is not
set; see experiments/src/experiments/montessori/README.md for the one-time
provisioning. A database that is not running is replaced by one in the demo's own
memory, so the run still sorts and the viewer's queries are still answered -- only its
recorded history is gone when it exits.
USAGE
}

for argument in "$@"; do
    case "$argument" in
        --no-browser) open_browser=0 ;;
        -h|--help) usage; exit 0 ;;
        *) demo_arguments+=("$argument") ;;
    esac
done

# a default the caller already decided about, either way, is theirs to decide
for default_argument in "${default_demo_arguments[@]}"; do
    if [[ "${default_argument}" == --no-* ]]; then
        negated_argument="--${default_argument#--no-}"
    else
        negated_argument="--no-${default_argument#--}"
    fi
    already_chosen=0
    for argument in ${demo_arguments[@]+"${demo_arguments[@]}"}; do
        if [[ "${argument}" == "${default_argument}" || "${argument}" == "${negated_argument}" ]]; then
            already_chosen=1
        fi
    done
    if [[ "${already_chosen}" -eq 0 ]]; then
        demo_arguments+=("${default_argument}")
    fi
done

# the interpreter this project is configured with, never a bare "python3" while a
# virtualenv is active or the repository ships its own
if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    python_executable="${VIRTUAL_ENV}/bin/python"
elif [[ -x "${repository_root}/.venv/bin/python" ]]; then
    python_executable="${repository_root}/.venv/bin/python"
else
    python_executable="$(command -v python3)"
fi
echo "Running with ${python_executable}."

# before anything else: say where this run's results go, and warn now rather than after
# the CRAM stack has imported and a world has been built, which costs a minute and
# buries the reason under a hundred-line traceback. No database problem stops the run --
# an unreachable one is replaced by an in-memory database and a read-only one is simply
# not recorded to -- so only a broken pre-flight itself does
if ! "${python_executable}" -m experiments.montessori.results_database \
    ${demo_arguments[@]+"${demo_arguments[@]}"}; then
    exit 1
fi

cramera_server_pid=""
stop_cramera_server() {
    if [[ -n "${cramera_server_pid}" ]] && kill -0 "${cramera_server_pid}" 2>/dev/null; then
        echo "Stopping the cramera server."
        kill "${cramera_server_pid}" 2>/dev/null || true
        wait "${cramera_server_pid}" 2>/dev/null || true
    fi
}
trap stop_cramera_server EXIT

echo "Starting the cramera server on port ${cramera_port}."
"${python_executable}" -m cramera.server &
cramera_server_pid=$!

# poll rather than sleep a fixed time: the server binds as soon as it is ready, and
# a demo started before that would come up with nothing to attach to
if ! "${python_executable}" - "${cramera_port}" "${server_startup_timeout_seconds}" <<'PY'
import socket
import sys
import time

port, timeout_seconds = int(sys.argv[1]), float(sys.argv[2])
deadline = time.monotonic() + timeout_seconds
while time.monotonic() < deadline:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            sys.exit(0)
    time.sleep(0.2)
sys.exit(1)
PY
then
    echo "The cramera server did not start within ${server_startup_timeout_seconds}s." >&2
    exit 1
fi

viewer_url="http://localhost:${cramera_port}/"
echo "Viewer ready at ${viewer_url}"
# no ?scene= on purpose: the viewer only attaches to a running demo by itself when
# the page names no recorded scene (see web/panels/robot_scene/panel.js)
echo "It attaches to the demo's bridge on port ${bridge_port} within a few seconds;"
echo "the EQL panel's buttons then answer from this run."

if [[ "${open_browser}" -eq 1 ]] && command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${viewer_url}" >/dev/null 2>&1 || true
fi

echo "Starting the demo."
demo_status=0
"${python_executable}" -m experiments.montessori.franka_montessori_demo --cramera \
    ${demo_arguments[@]+"${demo_arguments[@]}"} || demo_status=$?

if [[ "${demo_status}" -ne 0 ]]; then
    echo >&2
    echo "The demo exited with status ${demo_status}." >&2
fi
exit "${demo_status}"
