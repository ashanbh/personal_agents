REPO := $(shell pwd)
PLIST := ai.bittlebits.fomi4me.digest
LAUNCH_AGENTS := $(HOME)/Library/LaunchAgents

.PHONY: build run app test test-swift test-python install-launchd uninstall-launchd health digest

build:
	cd app && swift build -c release

run: build
	./app/.build/release/FomiForMe

# Assemble a double-clickable dist/FomiForMe.app (menu-bar agent).
app:
	bash scripts/make_app.command && open dist/FomiForMe.app
	@echo "Built dist/FomiForMe.app — double-click it in Finder, or drag to /Applications."

test: test-python test-swift

test-python:
	python3 -m pytest tests/ -q

test-swift:
	cd app && swift test

digest:
	python3 src/digest_builder.py

health:
	python3 argus/src/check_health.py

install-launchd:
	sed 's|__REPO__|$(REPO)|g' src/launchd/$(PLIST).plist > $(LAUNCH_AGENTS)/$(PLIST).plist
	launchctl unload $(LAUNCH_AGENTS)/$(PLIST).plist 2>/dev/null || true
	launchctl load $(LAUNCH_AGENTS)/$(PLIST).plist
	@echo "Digest scheduled daily at 18:00."

uninstall-launchd:
	launchctl unload $(LAUNCH_AGENTS)/$(PLIST).plist 2>/dev/null || true
	rm -f $(LAUNCH_AGENTS)/$(PLIST).plist
