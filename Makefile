# Build a single combined wordlist and the precompiled neovim spell file.
#
#   make refresh   # re-scrape wordlists/*.words from upstream sources
#   make build     # combine into programming.words and programming.utf-8.spl
#   make all       # refresh + build
#   make clean     # remove built artifacts (not the source wordlists)

.PHONY: all refresh build clean

WORDS_FILE := programming.words
SPL_FILE   := programming.utf-8.spl
SOURCES    := $(wildcard wordlists/*.words)

all: refresh build

refresh:
	scripts/update-all

build: $(SPL_FILE)

$(WORDS_FILE): $(SOURCES)
	cat $(SOURCES) > $@

$(SPL_FILE): $(WORDS_FILE)
	# :mkspell! writes <output-basename>.<encoding>.spl; nvim's default
	# encoding is utf-8, so we end up with programming.utf-8.spl directly.
	nvim --headless --clean \
	    -c "mkspell! programming $(WORDS_FILE)" \
	    -c "qa" 2>/dev/null

clean:
	rm -f $(WORDS_FILE) $(SPL_FILE)
