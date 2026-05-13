# dirtytalk

A spellcheck dictionary for programmers — fork of [psliwka/vim-dirtytalk][upstream]
with the vim plugin layer stripped out and a CI build that publishes the
compiled spell file as a release artifact you can drop into your editor.

[upstream]: https://github.com/psliwka/vim-dirtytalk

## What this is

- `wordlists/*.words` — per-topic source lists (acronyms, kubernetes, python,
  unix, etc.). Updated daily by CI from upstream sources (Wikipedia,
  cpython glossary, kubernetes openapi spec, …).
- `programming.words` — all wordlists concatenated.
- `programming.utf-8.spl` — neovim/vim binary spell file, compiled from
  `programming.words` via `:mkspell!`.

## Use it in (neo)vim

Drop the precompiled spell file into your nvim spell directory:

```sh
mkdir -p ~/.config/nvim/spell
curl -L -o ~/.config/nvim/spell/programming.utf-8.spl \
  https://raw.githubusercontent.com/vincentqb/dirtytalk/master/programming.utf-8.spl
```

Then in your config:

```vim
set spelllang=en,programming
set spell
```

That's it. No plugin, no `:DirtytalkUpdate`. The CI keeps the published
`.spl` fresh on a daily schedule.

## Build locally

```sh
make refresh   # re-scrape wordlists/ from upstream sources (needs curl, jq)
make build     # combine into programming.words and programming.utf-8.spl
make all       # both
make clean
```

`make build` only needs `nvim`. `make refresh` needs `curl` and `jq` and
talks to the internet.

## Adding a new wordlist source

Drop a script at `scripts/update-<topic>` following the pattern of the
existing ones (`source common.sh`, fetch a URL, pipe through `emit_words`).
The CI's `make refresh` step will pick it up automatically; the next CI
run produces an updated `.spl`.

## License

MIT — see [LICENSE](LICENSE). Wordlists derived from upstream sources;
see the credits section in [upstream's README][upstream-readme] for
attribution.

[upstream-readme]: https://github.com/psliwka/vim-dirtytalk#credits
