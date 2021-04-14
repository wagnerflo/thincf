% require for_files
% require show_diff

## load applied and see if there such a state
% do load_applied()

if [ -z "${applied}" ]; then
    printf 'No state applied; use "apply" subcommand first.\n'
    exit 1
fi

run () {
    for_files ${applied} show_diff csp file
}

if [ -t 1 ]; then
    run | less -r
else
    run
fi
