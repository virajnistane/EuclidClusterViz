_clusterviz_launch_completion() {
    local current_word previous_word options
    current_word="${COMP_WORDS[COMP_CWORD]}"
    previous_word="${COMP_WORDS[COMP_CWORD-1]}"
    options="--config --clear-cache --test-dependencies --help --debug --external --remote"

    if [[ "$previous_word" == "--config" ]]; then
        mapfile -t COMPREPLY < <(compgen -f -- "$current_word")
        return
    fi

    mapfile -t COMPREPLY < <(compgen -W "$options" -- "$current_word")
}

complete -o filenames -F _clusterviz_launch_completion launch.sh ./launch.sh
