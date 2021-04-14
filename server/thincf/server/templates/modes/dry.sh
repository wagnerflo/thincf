% require for_files
% require show_diff

## automatic fetch enable?
% if args.fetch
%   do install_csp()
% endif

## load latest and see if there such a state
% do load_latest()

if [ -z "${latest}" ]; then
    printf 'No latest state known; use "fetch" subcommand first.\n'
    exit 1
fi

run () {
    for_files ${latest} show_diff file csp
}

if [ -t 1 ]; then
    run | less -r
else
    run
fi
