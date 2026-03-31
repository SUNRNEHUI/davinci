#!/bin/sh
set -eu

VERSION="${DAVINCI_VERSION:-v1}"
ASSET_NAME="${DAVINCI_ASSET_NAME:-davinci-macos-v1.zip}"
RELEASE_URL="${DAVINCI_RELEASE_URL:-}"
INSTALL_ROOT="${DAVINCI_INSTALL_ROOT:-$HOME/.local/share/davinci}"
BIN_DIR="${DAVINCI_BIN_DIR:-$HOME/.local/bin}"
TMP_DIR="${TMPDIR:-/tmp}"
PACKAGE_NAME="${DAVINCI_PACKAGE_NAME:-davinci-cli}"
SOURCE_REF="${DAVINCI_SOURCE_REF:-main}"
SOURCE_URL="${DAVINCI_SOURCE_URL:-https://github.com/SUNRNEHUI/davinci/archive/refs/heads/${SOURCE_REF}.zip}"

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

detect_platform() {
  OS_NAME="$(uname -s)"
  ARCH_NAME="$(uname -m)"
  export OS_NAME ARCH_NAME
}

resolve_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_CMD="$candidate"
      export PYTHON_CMD
      return 0
    fi
  done
  fail "python3 or python is required for macOS source installation."
}

binary_mode_requested() {
  [ -n "$RELEASE_URL" ] || [ -n "${DAVINCI_RELEASE_BASE_URL:-}" ]
}

binary_mode_supported() {
  [ "${OS_NAME:-}" = "Darwin" ] && [ "${ARCH_NAME:-}" = "arm64" ]
}

resolve_release_url() {
  if [ -n "$RELEASE_URL" ]; then
    printf '%s\n' "$RELEASE_URL"
    return 0
  fi

  if [ -n "${DAVINCI_RELEASE_BASE_URL:-}" ]; then
    printf '%s/%s\n' "${DAVINCI_RELEASE_BASE_URL%/}" "$ASSET_NAME"
    return 0
  fi

  fail "release URL is not configured. Set DAVINCI_RELEASE_URL or DAVINCI_RELEASE_BASE_URL before running installer."
}

download_release() {
  url="$1"
  zip_path="$2"
  log "Downloading DAVINCI from:"
  log "  $url"
  curl -fsSL "$url" -o "$zip_path"
}

install_release() {
  zip_path="$1"
  target_dir="$2"
  rm -rf "$target_dir"
  mkdir -p "$target_dir"
  unzip -oq "$zip_path" -d "$target_dir"
}

resolve_bundle_dir() {
  parent="$1"
  matches="$(find "$parent" -maxdepth 2 -type f -name davinci | head -n 1 || true)"
  [ -n "$matches" ] || fail "could not find DAVINCI binary after unzip"
  dirname "$matches"
}

link_binary() {
  bundle_dir="$1"
  mkdir -p "$BIN_DIR"
  ln -sf "$bundle_dir/davinci" "$BIN_DIR/davinci"
}

write_app_launcher() {
  bundle_dir="$1"
  app_dir="$HOME/Applications"
  mkdir -p "$app_dir"
  launcher="$app_dir/DAVINCI.command"
  cat >"$launcher" <<EOF
#!/bin/zsh
set -e
exec "$bundle_dir/DAVINCI.command"
EOF
  chmod +x "$launcher"
}

print_binary_next_steps() {
  bundle_dir="$1"
  log ""
  log "DAVINCI installed."
  log "Bundle: $bundle_dir"
  log "CLI:    $BIN_DIR/davinci"
  log "Open:   $HOME/Applications/DAVINCI.command"
  log ""
  log "If $BIN_DIR is already in your PATH, run:"
  log "  davinci"
  log ""
  log "Otherwise run directly:"
  log "  $BIN_DIR/davinci"
}

ensure_pipx() {
  if "$PYTHON_CMD" -m pipx --version >/dev/null 2>&1; then
    return 0
  fi
  log "Installing pipx for the current user..."
  "$PYTHON_CMD" -m pip install --user --upgrade pipx
}

install_from_source() {
  resolve_python
  need_cmd curl
  ensure_pipx
  "$PYTHON_CMD" -m pipx ensurepath >/dev/null 2>&1 || true
  package_spec="${PACKAGE_NAME} @ ${SOURCE_URL}"
  log "Installing DAVINCI CLI via pipx from:"
  log "  $SOURCE_URL"
  "$PYTHON_CMD" -m pipx install --force "$package_spec"
  log ""
  log "DAVINCI installed via pipx."
  log "Command: davinci"
  log ""
  log "If your shell cannot find \`davinci\` yet, open a new terminal or run:"
  log "  $PYTHON_CMD -m pipx ensurepath"
}

install_from_binary() {
  need_cmd curl
  need_cmd unzip
  need_cmd find

  url="$(resolve_release_url)"
  work_dir="$(mktemp -d "$TMP_DIR/davinci-install.XXXXXX")"
  trap 'rm -rf "$work_dir"' EXIT INT TERM

  zip_path="$work_dir/$ASSET_NAME"
  release_root="$INSTALL_ROOT/$VERSION"
  install_parent="$release_root/unpacked"

  download_release "$url" "$zip_path"
  install_release "$zip_path" "$install_parent"
  bundle_dir="$(resolve_bundle_dir "$install_parent")"
  link_binary "$bundle_dir"
  write_app_launcher "$bundle_dir"
  print_binary_next_steps "$bundle_dir"
}

main() {
  detect_platform

  if binary_mode_requested; then
    binary_mode_supported || fail "Binary installer currently supports macOS Apple Silicon only."
    install_from_binary
    return 0
  fi

  case "${OS_NAME:-}" in
    Darwin)
      install_from_source
      ;;
    *)
      fail "install.sh currently supports macOS only."
      ;;
  esac
}

main "$@"
