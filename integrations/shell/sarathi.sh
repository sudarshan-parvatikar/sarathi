# shellcheck shell=sh
# Opt-in Bash/Zsh conveniences. Source this file from an interactive shell.
# All durable behavior remains in the sarathi program; these are thin helpers.

alias sr='sarathi'
alias srp='sarathi --profile personal'
alias srw='sarathi --profile work'
alias srn='sarathi --profile neutral'

sarathi_personal() {
  sarathi --profile personal "$@"
}

sarathi_work() {
  sarathi --profile work "$@"
}

sarathi_neutral() {
  sarathi --profile neutral "$@"
}

sarathi_here() {
  sarathi open "$PWD" --intent "$*"
}

sarathi_done() {
  sarathi complete "$@"
}

sarathi_personal_here() {
  sarathi --profile personal open "$PWD" --intent "$*"
}

sarathi_work_here() {
  sarathi --profile work open "$PWD" --intent "$*"
}
