#!/bin/bash
# Double-click this file in Finder to run a position check by hand.
set -u
cd "$(dirname "$0")" || exit 1

PYTHON=$(command -v python3) || {
    echo "python3 not found. Install Python 3.10 or newer and try again."
    read -r -p "Press Enter to close. "
    exit 1
}

# Each line of --list-apps is "<app_id>  <name>", after a "Projects:" header.
apps=()
while IFS= read -r line; do
    [[ $line =~ ^[0-9]+[[:space:]] ]] && apps+=("$line")
done < <("$PYTHON" -m app_store_rank_bot --list-apps)

if [ ${#apps[@]} -eq 0 ]; then
    echo "No projects found. Add an app first with: python3 -m app_store_rank_bot --app <app_id>"
    read -r -p "Press Enter to close. "
    exit 1
fi

echo "ASO Bot Parser — check positions"
echo
for i in "${!apps[@]}"; do
    printf "%d. %s\n" "$((i + 1))" "${apps[$i]}"
done
echo "a. All apps"
echo

read -r -p "Choose [1-${#apps[@]}, a]: " choice

selected=()
if [ "$choice" = "a" ] || [ "$choice" = "A" ]; then
    selected=("${apps[@]}")
elif [[ $choice =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#apps[@]} ]; then
    selected=("${apps[$((choice - 1))]}")
else
    echo "Unknown choice: $choice"
    read -r -p "Press Enter to close. "
    exit 1
fi

status=0
for app in "${selected[@]}"; do
    app_id=${app%% *}
    echo
    echo "=== $app"
    "$PYTHON" -m app_store_rank_bot --app "$app_id" --check-new-positions || status=1
done

echo
[ $status -eq 0 ] || echo "Some checks failed — see the output above."
read -r -p "Press Enter to close. "
exit $status
