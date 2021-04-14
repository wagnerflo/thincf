cat <<{% heredoc %}{{ args.message }}
{{ args.usage }}{% endheredoc -%}
exit 1
