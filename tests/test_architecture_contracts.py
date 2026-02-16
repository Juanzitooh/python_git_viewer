#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT_DIR / "viewer" / "core"
MAIN_FILE = ROOT_DIR / "main.py"

FORBIDDEN_TOP_LEVEL_IMPORTS = {
    "tkinter",
    "PySide6",
}

FORBIDDEN_PREFIXES = (
    "viewer.pyside",
)


def _iter_python_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.py") if path.is_file())


class TestArchitectureContracts(unittest.TestCase):
    def test_core_does_not_import_ui_toolkits(self) -> None:
        core_files = _iter_python_files(CORE_DIR)
        self.assertGreater(len(core_files), 0, "viewer/core sem modulos Python para validar.")

        for file_path in core_files:
            with self.subTest(file=file_path.name):
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(file_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name.strip()
                            top_level = module_name.split(".", 1)[0]
                            self.assertNotIn(
                                top_level,
                                FORBIDDEN_TOP_LEVEL_IMPORTS,
                                f"Import proibido em {file_path.name}: {module_name}",
                            )
                            self.assertFalse(
                                module_name.startswith(FORBIDDEN_PREFIXES),
                                f"Import proibido em {file_path.name}: {module_name}",
                            )
                    elif isinstance(node, ast.ImportFrom):
                        module_name = (node.module or "").strip()
                        if not module_name:
                            continue
                        top_level = module_name.split(".", 1)[0]
                        self.assertNotIn(
                            top_level,
                            FORBIDDEN_TOP_LEVEL_IMPORTS,
                            f"Import proibido em {file_path.name}: from {module_name} import ...",
                        )
                        self.assertFalse(
                            module_name.startswith(FORBIDDEN_PREFIXES),
                            f"Import proibido em {file_path.name}: from {module_name} import ...",
                        )

    def test_entrypoint_targets_pyside_shell(self) -> None:
        source = MAIN_FILE.read_text(encoding="utf-8")
        self.assertIn(
            "from viewer.pyside import shell",
            source,
            "main.py deve apontar para o shell PySide6.",
        )
        self.assertNotIn(
            "from viewer import app",
            source,
            "main.py nao deve mais importar frontend legado.",
        )


if __name__ == "__main__":
    unittest.main()
