#!/usr/bin/env sh

# macOS/Linux environment bootstrap for the HPA Fairing Optimization Project.
# Preferred usage:
#   source activate_env.sh

_hpa_note() {
    printf '%s\n' "$*"
}

_hpa_warn() {
    printf 'WARNING: %s\n' "$*" >&2
}

_hpa_error() {
    printf 'ERROR: %s\n' "$*" >&2
}

_hpa_append_path_var() {
    var_name="$1"
    candidate="$2"

    [ -n "$candidate" ] || return 0
    [ -e "$candidate" ] || return 0

    eval "current_value=\${$var_name:-}"
    case ":$current_value:" in
        *":$candidate:"*) return 0 ;;
    esac

    if [ -n "$current_value" ]; then
        eval "export $var_name=\"\$current_value:\$candidate\""
    else
        eval "export $var_name=\"\$candidate\""
    fi
}

_hpa_is_sourced() {
    if [ -n "${BASH_VERSION:-}" ] && [ "${BASH_SOURCE:-$0}" != "$0" ]; then
        return 0
    fi

    if [ -n "${ZSH_VERSION:-}" ]; then
        case "${ZSH_EVAL_CONTEXT:-}" in
            *:file) return 0 ;;
        esac
    fi

    return 1
}

_hpa_script_path() {
    if [ -n "${BASH_VERSION:-}" ]; then
        printf '%s\n' "${BASH_SOURCE:-$0}"
        return
    fi

    if [ -n "${ZSH_VERSION:-}" ]; then
        printf '%s\n' "${(%):-%N}"
        return
    fi

    printf '%s\n' "$0"
}

_hpa_find_openvsp_root_from_marker() {
    marker="$1"
    marker_dir=$(dirname "$marker")

    if [ "$(basename "$marker_dir")" = "openvsp" ]; then
        dirname "$marker_dir"
    else
        printf '%s\n' "$marker_dir"
    fi
}

_hpa_find_openvsp_in_app() {
    app_path="$1"
    [ -d "$app_path" ] || return 1

    marker=$(
        find "$app_path" -type f \
            \( -path '*/openvsp/__init__.py' -o -name 'openvsp.py' -o -name 'openvsp*.so' -o -name '_vsp*.so' \) \
            -print 2>/dev/null | head -n 1
    )

    [ -n "$marker" ] || return 1
    _hpa_find_openvsp_root_from_marker "$marker"
}

_hpa_discover_openvsp_python_root() {
    if [ -n "${OPENVSP_PYTHON_PATH:-}" ] && [ -d "${OPENVSP_PYTHON_PATH}" ]; then
        printf '%s\n' "${OPENVSP_PYTHON_PATH}"
        return 0
    fi

    if [ -n "${OPENVSP_APP:-}" ]; then
        root=$(_hpa_find_openvsp_in_app "${OPENVSP_APP}") || return 1
        printf '%s\n' "$root"
        return 0
    fi

    for base_dir in "/Applications" "$HOME/Applications" /Volumes/*/Applications; do
        [ -d "$base_dir" ] || continue

        app_path=$(find "$base_dir" -maxdepth 2 -type d -name 'OpenVSP*.app' -print 2>/dev/null | head -n 1)
        if [ -n "$app_path" ]; then
            root=$(_hpa_find_openvsp_in_app "$app_path") || continue
            printf '%s\n' "$root"
            return 0
        fi
    done

    for release_dir in /Volumes/*/Applications/OpenVSP*-MacOS; do
        [ -d "$release_dir/python" ] || continue

        marker=$(
            find "$release_dir/python" -maxdepth 3 -type f \
                \( -path '*/openvsp/__init__.py' -o -name 'openvsp.py' -o -name 'openvsp*.so' -o -name '_vsp*.so' \) \
                -print 2>/dev/null | head -n 1
        )

        if [ -n "$marker" ]; then
            _hpa_find_openvsp_root_from_marker "$marker"
            return 0
        fi
    done

    return 1
}

_hpa_discover_local_su2_bin() {
    su2_root="$PROJECT_ROOT/tools/su2"
    [ -d "$su2_root" ] || return 1

    for candidate in "$su2_root"/*/bin; do
        [ -d "$candidate" ] || continue
        if [ -x "$candidate/SU2_CFD" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    return 1
}

_hpa_python_has_module() {
    module_name="$1"

    python - "$module_name" <<'PY' >/dev/null 2>&1
import importlib.util
import sys

module_name = sys.argv[1]
raise SystemExit(0 if importlib.util.find_spec(module_name) else 1)
PY
}

_hpa_install_requirements_if_needed() {
    requirements_file="$1"
    [ -f "$requirements_file" ] || return 0

    missing_modules=""
    for module_name in numpy scipy pymoo matplotlib triangle gmsh meshio; do
        if ! _hpa_python_has_module "$module_name"; then
            missing_modules="$missing_modules $module_name"
        fi
    done

    if [ -n "$missing_modules" ]; then
        _hpa_note "Installing Python dependencies from requirements.txt..."
        python -m pip install -r "$requirements_file" || return 1
    else
        _hpa_note "Python dependencies already satisfied."
    fi
}

SCRIPT_PATH=$(_hpa_script_path)
PROJECT_ROOT=$(cd "$(dirname "$SCRIPT_PATH")" && pwd)
VENV_DIR="${VENV_DIR:-$PROJECT_ROOT/vsp_env}"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
WAS_SOURCED=0

if _hpa_is_sourced; then
    WAS_SOURCED=1
fi

if ! command -v python3 >/dev/null 2>&1; then
    _hpa_error "python3 not found. Please install Python 3.11 first."
    if [ "$WAS_SOURCED" -eq 1 ]; then
        return 1
    fi
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    _hpa_note "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR" || {
        if [ "$WAS_SOURCED" -eq 1 ]; then
            return 1
        fi
        exit 1
    }
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate" || {
    _hpa_error "Failed to activate virtual environment: $VENV_DIR"
    if [ "$WAS_SOURCED" -eq 1 ]; then
        return 1
    fi
    exit 1
}

python -m pip install --upgrade pip >/dev/null 2>&1
_hpa_install_requirements_if_needed "$REQUIREMENTS_FILE" || {
    if [ "$WAS_SOURCED" -eq 1 ]; then
        return 1
    fi
    exit 1
}

OPENVSP_ROOT=""
if _hpa_python_has_module openvsp; then
    _hpa_note "openvsp is already importable in the active environment."
else
    OPENVSP_ROOT=$(_hpa_discover_openvsp_python_root 2>/dev/null || true)

    if [ -n "$OPENVSP_ROOT" ]; then
        _hpa_append_path_var PYTHONPATH "$OPENVSP_ROOT"
        _hpa_append_path_var DYLD_FALLBACK_LIBRARY_PATH "$(dirname "$OPENVSP_ROOT")"
        _hpa_append_path_var DYLD_FALLBACK_LIBRARY_PATH "$(dirname "$(dirname "$OPENVSP_ROOT")")/MacOS"
        _hpa_append_path_var PATH "$(dirname "$(dirname "$OPENVSP_ROOT")")/MacOS"
        _hpa_note "Detected OpenVSP Python API under: $OPENVSP_ROOT"
    fi
fi

LOCAL_SU2_BIN=$(_hpa_discover_local_su2_bin 2>/dev/null || true)
if [ -n "$LOCAL_SU2_BIN" ]; then
    _hpa_append_path_var PATH "$LOCAL_SU2_BIN"
    _hpa_append_path_var PYTHONPATH "$LOCAL_SU2_BIN"
    export SU2_RUN="$LOCAL_SU2_BIN"
    _hpa_note "Detected local SU2 tools under: $LOCAL_SU2_BIN"
fi

if python - <<'PY' >/dev/null 2>&1
import openvsp as vsp
print(vsp.__file__)
PY
then
    OPENVSP_MODULE_PATH=$(python - <<'PY'
import openvsp as vsp
print(vsp.__file__)
PY
)
    _hpa_note "OpenVSP import check: OK"
    _hpa_note "openvsp module: $OPENVSP_MODULE_PATH"
else
    _hpa_warn "OpenVSP is still not importable."
    _hpa_warn "Install OpenVSP.app and then re-run: source activate_env.sh"
    _hpa_warn "You can also set OPENVSP_APP=/Applications/OpenVSP.app or OPENVSP_PYTHON_PATH=/path/to/openvsp/python"
fi

export HPA_PROJECT_ROOT="$PROJECT_ROOT"

_hpa_note ""
_hpa_note "Environment ready."
_hpa_note "Project root: $PROJECT_ROOT"
_hpa_note "Python: $(python --version 2>&1)"
_hpa_note "Try: python scripts/run_ga.py --config config/ga_config.json"

if [ "$WAS_SOURCED" -ne 1 ]; then
    _hpa_warn "This script was executed, not sourced. Run 'source activate_env.sh' to keep the environment in your current shell."
fi
