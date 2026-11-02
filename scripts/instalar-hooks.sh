#!/bin/sh
# Activa los hooks versionados del repo (commit-msg).
cd "$(dirname "$0")/.." || exit 1
git config core.hooksPath .githooks
chmod +x .githooks/*
echo "Hooks activados: core.hooksPath = .githooks"
