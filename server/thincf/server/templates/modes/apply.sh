% require for_files
% require apply_functions
% require link_latest
% require iso8601
% require list_contains
% require run_with_files

## automatic fetch enable?
% if args.fetch
%   do install_csp()
% endif

## load latest and see if there such a state
% do load_latest()

if [ -z ${latest} ]; then
    printf 'No latest state known; use "fetch" subcommand first.\n'
    exit 1
fi

print_header () {
    [ ${header_printed} -ne 0 ] && return
    printf %b "${header}"
    header_printed=1
}

print_footer () {
    [ ${header_printed} -eq 0 ] && return
    printf %b "$1"
}

print_type_diff () {
    print_header
    printf ' \043 %s' "${csp_type}"
}

print_mode_diff () {
    print_header
    printf ' \043 %s' "${csp_mode}"
}

print_owner_diff () {
    print_header
    printf ' \043 %s' "${csp_user}:${csp_group}"
}

print_target_diff () {
    print_header
    printf ' \043 -> %s' "${csp_target}"
}

print_content_diff () {
    print_header
    printf ' \043 -%s +%s' "${file_diff_del}" "${file_diff_ins}"
}

type_changed () {
    [ "${csp_type}" != "${file_type}" ]
}

mode_changed() {
    [ "${csp_mode}" != "${file_mode}" ]
}

owner_changed () {
    [ "${csp_user}"  != "${file_user}" -o \
      "${csp_group}" != "${file_group}" ]
}

target_changed () {
    [ "${csp_type}" = "symlink" -a \
      "${csp_target}" != "${file_target}" ]
}

content_changed () {
    [ "${csp_type}" = "file" -a \
      \( ${file_diff_del} -ne 0 -o ${file_diff_ins} -ne 0 \) ]
}

file_missing () {
    [ "${file_type}" = "missing" ]
}

found_modified=0
found_protected=0

## overwrite disabled?
% if not args.overwrite
%   do load_applied()
find_modified () {
    local header header_printed
    header="${file} \043 modified"
    header_printed=0

    file_missing    && return
    type_changed    && print_type_diff
    mode_changed    && print_mode_diff
    owner_changed   && print_owner_diff
    target_changed  && print_target_diff
    content_changed && print_content_diff

    print_footer "\n"

    if [ ${header_printed} -ne 0 ]; then
        found_modified=1
    fi
}

if [ -n "${applied}" ]; then
    for_files ${applied} find_modified

    if [ ${found_modified} -ne 0 ]; then
        cat <<EOF

By default thincf will not touch files and directories with local
modifications. If you want to disable this fail-safe use the "-o"
commandline option.

EOF
    fi
fi
% endif

## fail-safe enabled?
% if not args.unsafe
%   require is_protected
find_protected () {
    if ! is_protected ${octfile}; then
       return 0
    fi

    local header header_printed
    header="${file} \043 protected"
    header_printed=0

    type_changed    && print_type_diff "${csp_mode}"
    mode_changed    && print_mode_diff
    owner_changed   && print_owner_diff
    target_changed  && print_target_diff
    content_changed && print_content_diff

    print_footer "\n"

    if [ ${header_printed} -ne 0 ]; then
        found_protected=1
    fi
}

for_files ${latest} find_protected

if [ ${found_protected} -ne 0 ]; then
    cat <<EOF

By default thincf will not touch critical files and directories to avoid
bricking the system. If you want to disable this fail-safe use the "-u"
commandline option.

EOF
fi
% endif

if [ ${found_modified} -ne 0 -o ${found_protected} -ne 0 ]; then
    exit 1
fi

## run prepare actions
prepare=""

collect_prepare () {
    for action in ${csp_actions}; do
        if ! list_contains ${action} ${prepare}; then
            prepare="${prepare} ${action}"
        fi
        eval prepare_${action}_files=\"\${prepare_${action}_files} ${octfile}\"
    done
}

for_files ${latest} collect_prepare

for action in ${prepare}; do
    eval run_with_files prepare \${prepare_${action}_files}
done

## apply all changes
bfile="${THINCF_BACKUPDIR}/$(make_iso8601).tar"
actions=""

before_change () {
    [ ${header_printed} -ne 0 ] && return

    if ! file_missing; then
        mode="-u"
        recurse="-n"

        [ ! -e "${bfile}" ] && mode="-c"
        type_changed && [ "${file_type}" = "dir" ] && recurse=""

        tar ${mode} -f "${bfile}" ${recurse} \
            -C "${THINCF_ROOT}" "${file#${THINCF_ROOT}}"
    fi

    ## take note of actions and the file that triggered it
    for action in ${csp_actions}; do
        if ! list_contains ${action} ${actions}; then
            actions="${actions} ${action}"
        fi
        eval action_${action}_files=\"\${action_${action}_files} ${octfile}\"
    done
}

apply_change () {
    local header header_printed
    header="${file}"
    header_printed=0

    if type_changed; then
        before_change
        delete_path "${file}"

        print_mode_diff
        print_owner_diff

        case "${csp_type}" in
            file)
                print_content_diff
                ${csp} cat ${octfile} | write_contents "${file}"
                ;;
            dir)
                create_directory "${file}"
                ;;
            symlink)
                print_target_diff
                create_symlink "${file}" "${csp_target}"
                ;;
        esac

        set_mode "${file}" "${csp_mode}"
        set_user "${file}" "${csp_user}"
        set_group "${file}" "${csp_group}"

    else
        if mode_changed; then
            before_change
            print_mode_diff
            set_mode "${file}" "${csp_mode}"
        fi

        if owner_changed; then
            before_change
            print_owner_diff
            set_user "${file}" "${csp_user}"
            set_group "${file}" "${csp_group}"
        fi

        if target_changed; then
            before_change
            print_target_diff
            create_symlink "${file}" "${csp_target}"
        fi

        if content_changed; then
            before_change
            print_content_diff
            ${csp} cat ${octfile} | write_contents "${file}"
        fi
    fi

    print_footer "\n"
}

for_files ${latest} apply_change

## action protocol
actions=$(printf '%s\n' ${actions} | sort -u)
applied_actions=""

run_actions () {
    ## run all actions in check mode first; this allows things like
    ## verifying configuration
    for action in ${actions}; do
        eval run_with_files check \${action_${action}_files} || \
            return 1
    done

    for action in ${actions}; do
        ## mark the action applied before actually running it; doing
        ## this irrespectivly of its success for failure makes sense
        ## because we'll want to rollback a action either way
        applied_actions="${applied_actions}${action}"

        ## now make the action do its dirty work
        eval run_with_files apply \${action_${action}_files} || \
            return 1

        ## run the action post verification
        eval run_with_files verify \${action_${action}_files} || \
            return 1
    done
}

if [ -z "${actions}" ]; then
    link_latest
else
    printf 'Running actions...\n'
    if run_actions; then
        link_latest
    else
        ## running one of the actions failed: roll back the changes
        printf 'Error in action; rolling back.\n'
        if [ -e "${bfile}" ]; then
            tar -x -f "${bfile}" --clear-nochange-fflags \
                -C "${THINCF_ROOT}"
        fi

        ## and rerun all actions that have been applied
        for action in ${applied_actions}; do
            eval run_with_files apply \${action_${action}_files} || \
                true
        done
    fi
fi
