"""Blueprint registry for Tier 7 integration exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

BlueprintSurface = Literal["ide", "desktop", "mobile", "chrome", "communication"]


@dataclass(frozen=True)
class BlueprintFile:
    """One file emitted by an integration blueprint."""

    relative_path: str
    content: str


@dataclass(frozen=True)
class IntegrationBlueprint:
    """Describes one exportable integration scaffold."""

    slug: str
    surface: BlueprintSurface
    name: str
    description: str
    files: tuple[BlueprintFile, ...]


def _json_document(payload: object) -> str:
    """Render one JSON document with stable formatting."""

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _yaml_document(payload: object) -> str:
    """Render one YAML document with stable formatting."""

    return yaml.safe_dump(payload, sort_keys=False)


_BLUEPRINTS: dict[str, IntegrationBlueprint] = {
    "vscode": IntegrationBlueprint(
        slug="vscode",
        surface="ide",
        name="VS Code extension",
        description="Minimal VS Code command surface for launching Henchman chat.",
        files=(
            BlueprintFile(
                "package.json",
                _json_document(
                    {
                        "name": "henchman-ai-vscode",
                        "displayName": "Henchman AI",
                        "version": "0.1.0",
                        "engines": {"vscode": "^1.90.0"},
                        "activationEvents": ["onCommand:henchman.openChat"],
                        "main": "./extension.js",
                        "contributes": {
                            "commands": [
                                {
                                    "command": "henchman.openChat",
                                    "title": "Henchman: Open Chat",
                                }
                            ]
                        },
                    },
                ),
            ),
            BlueprintFile(
                "extension.js",
                """const vscode = require("vscode");

function activate(context) {
  const disposable = vscode.commands.registerCommand("henchman.openChat", async () => {
    const terminal = vscode.window.createTerminal("Henchman AI");
    terminal.show();
    terminal.sendText("henchman chat");
  });

  context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
""",
            ),
        ),
    ),
    "jetbrains": IntegrationBlueprint(
        slug="jetbrains",
        surface="ide",
        name="JetBrains plugin",
        description="Minimal IntelliJ plugin descriptor for launching Henchman chat.",
        files=(
            BlueprintFile(
                "plugin.xml",
                """<idea-plugin>
  <id>ai.henchman.jetbrains</id>
  <name>Henchman AI</name>
  <vendor email="support@example.com">Henchman AI</vendor>
  <description>Launches Henchman chat from the IDE.</description>
  <depends>com.intellij.modules.platform</depends>
</idea-plugin>
""",
            ),
            BlueprintFile(
                "build.gradle.kts",
                """plugins {
    id("org.jetbrains.intellij") version "1.17.4"
    kotlin("jvm") version "1.9.24"
}

group = "ai.henchman"
version = "0.1.0"
""",
            ),
        ),
    ),
    "electron": IntegrationBlueprint(
        slug="electron",
        surface="desktop",
        name="Electron desktop app",
        description="Desktop shell that embeds Henchman web/chat surfaces.",
        files=(
            BlueprintFile(
                "package.json",
                _json_document(
                    {
                        "name": "henchman-desktop",
                        "version": "0.1.0",
                        "private": True,
                        "main": "main.js",
                        "scripts": {"start": "electron ."},
                        "devDependencies": {"electron": "^31.0.0"},
                    },
                ),
            ),
            BlueprintFile(
                "main.js",
                """const { BrowserWindow, app } = require("electron");

function createWindow() {
  const window = new BrowserWindow({
    width: 1280,
    height: 820,
  });

  window.loadURL("http://127.0.0.1:8000");
}

app.whenReady().then(createWindow);
""",
            ),
        ),
    ),
    "react-native": IntegrationBlueprint(
        slug="react-native",
        surface="mobile",
        name="React Native companion",
        description="Minimal mobile companion scaffold for remote Henchman sessions.",
        files=(
            BlueprintFile(
                "app.json",
                _json_document(
                    {
                        "expo": {
                            "name": "Henchman Mobile",
                            "slug": "henchman-mobile",
                            "version": "0.1.0",
                        }
                    },
                ),
            ),
            BlueprintFile(
                "App.js",
                """import React from "react";
import { SafeAreaView, Text } from "react-native";

export default function App() {
  return (
    <SafeAreaView style={{ flex: 1, justifyContent: "center", alignItems: "center" }}>
      <Text>Henchman Mobile Companion</Text>
    </SafeAreaView>
  );
}
""",
            ),
        ),
    ),
    "chrome-extension": IntegrationBlueprint(
        slug="chrome-extension",
        surface="chrome",
        name="Chrome extension",
        description="Manifest v3 side-panel scaffold for capturing web context.",
        files=(
            BlueprintFile(
                "manifest.json",
                _json_document(
                    {
                        "manifest_version": 3,
                        "name": "Henchman AI",
                        "version": "0.1.0",
                        "permissions": ["activeTab", "sidePanel", "storage"],
                        "background": {"service_worker": "service-worker.js"},
                        "side_panel": {"default_path": "sidepanel.html"},
                    },
                ),
            ),
            BlueprintFile(
                "service-worker.js",
                """chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});
""",
            ),
            BlueprintFile(
                "sidepanel.html",
                """<!doctype html>
<html>
  <body>
    <h1>Henchman AI</h1>
    <script src="sidepanel.js"></script>
  </body>
</html>
""",
            ),
            BlueprintFile(
                "sidepanel.js",
                """console.log("Henchman side panel ready");""",
            ),
        ),
    ),
    "slack-app": IntegrationBlueprint(
        slug="slack-app",
        surface="communication",
        name="Slack app manifest",
        description="Slack app manifest for wiring Henchman slash commands and bot scopes.",
        files=(
            BlueprintFile(
                "manifest.yaml",
                _yaml_document(
                    {
                        "display_information": {"name": "Henchman AI"},
                        "features": {
                            "bot_user": {"display_name": "Henchman AI"},
                            "slash_commands": [
                                {
                                    "command": "/henchman",
                                    "description": "Ask Henchman AI for help",
                                    "usage_hint": "[prompt]",
                                    "should_escape": False,
                                }
                            ],
                        },
                        "oauth_config": {
                            "scopes": {
                                "bot": [
                                    "app_mentions:read",
                                    "channels:history",
                                    "chat:write",
                                    "commands",
                                    "im:history",
                                ]
                            }
                        },
                    },
                ),
            ),
        ),
    ),
}


def list_blueprints(surface: BlueprintSurface | None = None) -> list[IntegrationBlueprint]:
    """Return registered blueprints, optionally filtered by one surface."""

    blueprints = list(_BLUEPRINTS.values())
    if surface is not None:
        blueprints = [blueprint for blueprint in blueprints if blueprint.surface == surface]
    return sorted(blueprints, key=lambda blueprint: (blueprint.surface, blueprint.slug))


def get_blueprint(slug: str) -> IntegrationBlueprint:
    """Return one blueprint by slug."""

    blueprint = _BLUEPRINTS.get(slug)
    if blueprint is None:
        msg = f"Unknown integration blueprint: {slug}"
        raise ValueError(msg)
    return blueprint


def export_blueprint(slug: str, destination: Path, *, force: bool = False) -> list[Path]:
    """Materialize one blueprint into the destination directory."""

    blueprint = get_blueprint(slug)
    resolved_destination = destination.resolve()
    resolved_destination.mkdir(parents=True, exist_ok=True)

    targets = [resolved_destination / file.relative_path for file in blueprint.files]
    if not force:
        for target in targets:
            if target.exists():
                msg = f"Refusing to overwrite existing file: {target.name}"
                raise FileExistsError(msg)

    written_paths: list[Path] = []
    for blueprint_file, target in zip(blueprint.files, targets, strict=True):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(blueprint_file.content, encoding="utf-8")
        written_paths.append(target)

    return written_paths


__all__ = [
    "IntegrationBlueprint",
    "export_blueprint",
    "get_blueprint",
    "list_blueprints",
]
