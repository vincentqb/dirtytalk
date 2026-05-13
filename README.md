# dirtytalk

Spellcheck dictionary for programmers. A fork of [psliwka/vim-dirtytalk][upstream]
that ships the compiled spell file directly, so you don't need a vim plugin.

[upstream]: https://github.com/psliwka/vim-dirtytalk

## Use in (neo)vim

```sh
mkdir -p ~/.config/nvim/spell
curl -L -o ~/.config/nvim/spell/programming.utf-8.spl \
  https://raw.githubusercontent.com/vincentqb/dirtytalk/master/programming.utf-8.spl
```

```vim
set spelllang=en,programming
set spell
```

## Build locally

```sh
uv run dirtytalk build
```

Requires `uv` and `nvim` (for `:mkspell!`).

## License

MIT — see [LICENSE](LICENSE).
