# dirtytalk

Spellcheck dictionary for programmers. A fork of [psliwka/vim-dirtytalk][upstream]
that ships the wordlist as plain text; you compile it once on install with
`:mkspell!`.

## Use in (neo)vim

Download the wordlist, then compile it once with your editor:

```sh
mkdir -p ~/.config/nvim/spell
curl -L -o ~/.config/nvim/spell/programming.words \
  https://raw.githubusercontent.com/vincentqb/dirtytalk/master/programming.words
nvim --headless -c \
  'mkspell! ~/.config/nvim/spell/programming ~/.config/nvim/spell/programming.words' \
  -c qa
```

In your config:

```vim
set spelllang=en,programming
set spell
```

## Build locally

```sh
uv run dirtytalk build    # concatenate wordlists/ into programming.words
uv run dirtytalk fetch    # refresh wordlists/ from upstream sources (network)
```

CI rebuilds yearly (Jan 1) and on demand via
`gh workflow run build.yml -f refresh=true`.

## License

MIT — see [LICENSE](LICENSE).

[upstream]: https://github.com/psliwka/vim-dirtytalk
