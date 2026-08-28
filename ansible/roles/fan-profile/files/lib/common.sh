normalize() {
    case "${1:-}" in
        quiet | silent | low-power | low_power | power-saver | powersave) echo quiet ;;
        balanced | default | auto | normal) echo balanced ;;
        performance | overboost | high-performance | turbo) echo performance ;;
        *) echo "${1:-}" ;;
    esac
}

resolve_choice() {
    local want c
    want=$(normalize "${1:-}")
    for c in $(adapter_choices); do
        [ "$(normalize "$c")" = "$want" ] && {
            echo "$c"
            return 0
        }
    done
    for want in quiet balanced performance; do
        for c in $(adapter_choices); do
            [ "$(normalize "$c")" = "$want" ] && {
                echo "$c"
                return 0
            }
        done
    done
    c=$(adapter_choices | head -n1)
    [ -n "$c" ] || return 1
    echo "$c"
}

hwmon_fans() {
    local hw f rpm label name
    for hw in /sys/class/hwmon/hwmon*; do
        [ -d "$hw" ] || continue
        for f in "$hw"/fan*_input; do
            [ -r "$f" ] || continue
            rpm=$(cat "$f" 2>/dev/null || true)
            case "$rpm" in
                '' | *[!0-9]*) rpm=0 ;;
            esac
            name=${f##*/fan}
            name=${name%_input}
            label=$(cat "${f%_input}_label" 2>/dev/null || true)
            if [ -n "$label" ]; then
                name=$(printf '%s' "$label" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9_' '_')
                name=${name%_fan}
                name=${name%_input}
                name=${name#_}
                [ -n "$name" ] || name=fan
            fi
            printf '%s\t%s\n' "$name" "$rpm"
        done
    done
}

pkg_temp() {
    local t= label f
    for f in /sys/class/hwmon/hwmon*/temp*_input; do
        [ -r "$f" ] || continue
        label=$(cat "${f%_input}_label" 2>/dev/null || true)
        case "$label" in
            *Package* | *package*) t=$(cat "$f" 2>/dev/null || true) && break ;;
        esac
    done
    if [ -z "$t" ]; then
        for f in /sys/class/hwmon/hwmon*/temp*_input; do
            [ -r "$f" ] || continue
            t=$(cat "$f" 2>/dev/null || true)
            break
        done
    fi
    case "$t" in
        '' | *[!0-9]*) t=0 ;;
    esac
    printf '%d' $((t / 1000))
}

json_str() {
    printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"
}

fan_status_json() {
    local line name rpm out first
    out=
    first=1
    while IFS=$'\t' read -r name rpm; do
        [ -n "$name" ] || continue
        [ "$first" -eq 1 ] || out="$out,"
        out="$out{\"name\":$(json_str "$name"),\"rpm\":$rpm}"
        first=0
    done < <(hwmon_fans)
    printf '%s' "$out"
}
