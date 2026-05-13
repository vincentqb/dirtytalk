# dirtytalk

A spellcheck dictionary for programmers — fork of [psliwka/vim-dirtytalk][upstream]
with the vim plugin layer stripped out and a CI build that publishes the
compiled spell file as a release artifact you can drop into your editor.

[upstream]: https://github.com/psliwka/vim-dirtytalk

## What this is

- `wordlists/*.words` — per-topic source lists (acronyms, kubernetes, python,
  unix, etc.). Currently checked in as captured from upstream + PR #45.
  Refresh from live sources will return in a Python rewrite (see ROADMAP
  below).
- `programming.words` — all wordlists concatenated.
- `programming.utf-8.spl` — neovim/vim binary spell file, compiled from
  `programming.words` via `:mkspell!`. Rebuilt by CI on every push.

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

That's it. No plugin, no `:DirtytalkUpdate`. CI rebuilds the published
`.spl` on every push.

## Build locally

```sh
make build     # combine wordlists/ into programming.words and .spl
make clean
```

`make build` only needs `nvim`. The `make refresh` step (re-scraping
upstream sources via `scripts/update-*`) is currently broken because
several of those upstream URLs/formats have changed — see ROADMAP.

## ROADMAP

- [x] Strip vim plugin layer; build via CI.
- [ ] Rewrite the per-source generators in Python (one file per source,
      one `build.py` driver). Replaces the bash + jq + Docker pipeline.
      Will fix the broken sources and re-enable a daily refresh.
- [ ] Publish the `.spl` as a GitHub Release artifact too.

## Adding a new wordlist source

Until the Python rewrite, just edit `wordlists/<topic>.words` directly
(plain text, one word per line). After the rewrite, you'll add a
`generators/<topic>.py` and the build will pick it up automatically.

## License

MIT — see [LICENSE](LICENSE). Wordlists derived from upstream sources;
see the credits section in [upstream's README][upstream-readme] for
attribution.

[upstream-readme]: https://github.com/psliwka/vim-dirtytalk#credits
