# shellcheck shell=sh
# Opt-in Bash/Zsh conveniences. Source this file from an interactive shell.
# All durable behavior remains in the sarathi program; these are thin helpers.

alias sr='sarathi'

sarathi_here() {
  sarathi open "$PWD" --intent "$*"
}

sarathi_done() {
  sarathi complete "$@"
}
