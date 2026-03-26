#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

log() { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Не найдена команда: $1"
}

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  if require_cmd sudo 2>/dev/null; then
    warn "Скрипт запущен не от root. Перезапуск через sudo..."
    exec sudo -E bash "$0" "$@"
  else
    die "Нужно запускать от root (или установить sudo)."
  fi
fi

TARGET_USER="${SUDO_USER:-${USER:-}}"
if [[ -z "${TARGET_USER}" || "${TARGET_USER}" == "root" ]]; then
  TARGET_USER="$(logname 2>/dev/null || true)"
fi
[[ -n "${TARGET_USER}" && "${TARGET_USER}" != "root" ]] || die "Не удалось определить пользователя для добавления в группу docker."

require_cmd id
require_cmd uname
require_cmd systemctl
require_cmd usermod
require_cmd groupadd || true
require_cmd sed
require_cmd awk

require_cmd curl
require_cmd gpg

if command -v dnf >/dev/null 2>&1; then
  PKG_MGR="dnf"
elif command -v yum >/dev/null 2>&1; then
  PKG_MGR="yum"
else
  die "Не найдена dnf или yum."
fi

if [[ ! -r /etc/os-release ]]; then
  die "Не удаётся прочитать /etc/os-release"
fi
# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID:-}" != "rocky" ]]; then
  warn "Обнаружен дистрибутив: ${ID:-unknown}. Скрипт предназначен для Rocky Linux 8/9."
fi

VERSION_ID_STR="${VERSION_ID:-}"
if [[ -z "${VERSION_ID_STR}" ]]; then
  die "Не удалось определить VERSION_ID из /etc/os-release"
fi
RELEASEVER="$(awk -F. '{print $1}' <<<"$VERSION_ID_STR")"
if [[ "$RELEASEVER" != "8" && "$RELEASEVER" != "9" ]]; then
  die "Неподдерживаемая версия Rocky/Linux: VERSION_ID=$VERSION_ID_STR (ожидались 8 или 9)."
fi

BASEARCH="$(uname -m)"
case "$BASEARCH" in
  x86_64|aarch64) ;;
  *)
    die "Неподдерживаемая архитектура: $BASEARCH"
    ;;
esac

log "Установка Docker Engine и docker compose plugin для Rocky Linux $RELEASEVER ($BASEARCH)..."

log "Установим зависимости..."
if [[ "$PKG_MGR" == "dnf" ]]; then
  "$PKG_MGR" -y install ca-certificates curl gpg2 || "$PKG_MGR" -y install ca-certificates curl gnupg2 || true
else
  "$PKG_MGR" -y install ca-certificates curl gpg2 || "$PKG_MGR" -y install ca-certificates curl gnupg2 || true
fi

require_cmd gpg

log "Проставим ключ Docker..."
mkdir -p /usr/share/keyrings
curl -fsSL "https://download.docker.com/linux/centos/gpg" | gpg --dearmor -o /usr/share/keyrings/docker.gpg

log "Добавим репозиторий Docker CE..."
cat >/etc/yum.repos.d/docker-ce.repo <<EOF
[docker-ce-stable]
name=Docker CE Stable - $BASEARCH
baseurl=https://download.docker.com/linux/centos/$RELEASEVER/$BASEARCH/stable
enabled=1
gpgcheck=1
gpgkey=file:///usr/share/keyrings/docker.gpg
EOF

log "Обновим индексы..."
if [[ "$PKG_MGR" == "dnf" ]]; then
  "$PKG_MGR" -y makecache
else
  "$PKG_MGR" -y makecache || true
fi

log "Удалим старые пакеты Docker (если были)..."
"$PKG_MGR" -y remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true

log "Установим Docker Engine и docker compose plugin..."
"$PKG_MGR" -y install \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-compose-plugin

log "Включаем и запускаем сервис docker..."
systemctl enable --now docker

log "Добавляем пользователя '$TARGET_USER' в группу 'docker'..."
if ! getent group docker >/dev/null 2>&1; then
  groupadd docker
fi

if id -nG "$TARGET_USER" | awk '{print}' | grep -qw docker; then
  log "Пользователь '$TARGET_USER' уже в группе docker."
else
  usermod -aG docker "$TARGET_USER"
  warn "Готово. Выполните перелогин (logout/login) для '$TARGET_USER', чтобы группа применилась."
fi

log "Проверка доступности docker..."
docker --version >/dev/null

log "Итог: Docker установлен и запущен, compose plugin доступен."

