"""Tests for scripts/deps.py. Run: python3 -m unittest discover -s tests (from the skill directory)."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import deps  # noqa: E402

CARGO_LOCK = """version = 3

[[package]]
name = "rustls"
version = "0.23.36"
source = "registry+https://github.com/rust-lang/crates.io-index"

[[package]]
name = "rustls"
version = "0.21.12"

[[package]]
name = "rustls-webpki"
version = "0.103.9"
"""

PNPM_V9 = """lockfileVersion: '9.0'

importers:
  .:
    dependencies:
      next:
        specifier: catalog:security
        version: 15.5.24(react@19.0.0)

packages:
  next@15.5.24:
    resolution: {integrity: sha512-x}
  '@scope/source-map-js@1.0.0':
    resolution: {integrity: sha512-y}
  source-map-js@1.2.1:
    resolution: {integrity: sha512-z}

snapshots:
  next@15.5.24(react@19.0.0):
    dependencies:
      source-map-js: 1.2.1
"""

PNPM_V6 = """lockfileVersion: '6.0'

packages:
  /source-map-js@1.0.2:
    resolution: {integrity: sha512-a}
  /left-pad/1.3.0:
    resolution: {integrity: sha512-b}
"""

PACKAGE_LOCK = {
    "lockfileVersion": 3,
    "packages": {
        "": {"name": "root"},
        "node_modules/braces": {"version": "3.0.3"},
        "node_modules/micromatch/node_modules/braces": {"version": "2.3.2"},
        "node_modules/@scope/pkg": {"version": "1.0.0"},
        "packages/local": {"version": "0.0.1", "link": True},
    },
}

YARN_CLASSIC = '''# yarn lockfile v1

"braces@^3.0.2", braces@~3.0.2:
  version "3.0.2"
  resolved "https://registry.yarnpkg.com/braces/-/braces-3.0.2.tgz"

"@scope/braces@^1.0.0":
  version "1.0.0"
'''

YARN_BERRY = '''__metadata:
  version: 8

"braces@npm:^3.0.3":
  version: 3.0.3
  resolution: "braces@npm:3.0.3"
'''

BUN_LOCK = '''{
  "lockfileVersion": 1,
  "packages": {
    "sharp": ["sharp@0.35.3", "", { "dependencies": { "detect-libc": "^2.1.2" } }, "sha512-a"],
    "next/sharp": ["sharp@0.34.5", "", {}, "sha512-b"],
    "@img/sharp-darwin-arm64": ["@img/sharp-darwin-arm64@0.35.3", "", {}, "sha512-c"],
  }
}
'''

GO_MOD = """module example.com/app

go 1.22

require (
\tgithub.com/jackc/pgx/v5 v5.7.1
\tgolang.org/x/crypto v0.31.0 // indirect
)

require github.com/stretchr/testify v1.9.0
"""


def make_repo(files: dict) -> Path:
    root = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content))
    return root


def run(root, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = deps.main([str(root), *args])
    return code, json.loads(out.getvalue()) if out.getvalue() else None


class Ranges(unittest.TestCase):
    def test_in_range(self):
        self.assertTrue(deps.in_range("1.2.1", ">= 1.0.0, < 1.2.2"))
        self.assertFalse(deps.in_range("1.2.2", ">= 1.0.0, < 1.2.2"))
        self.assertFalse(deps.in_range("0.6.2", ">= 1.0.0, < 1.2.2"))
        self.assertTrue(deps.in_range("4.2.0", "<= 4.2.0"))
        self.assertTrue(deps.in_range("0.26.0-beta.3", ">= 0.26.0-beta.1, < 0.26.2"))
        with self.assertRaises(ValueError):
            deps.in_range("1.0.0", "garbage")

    def test_judge_by_major_line(self):
        self.assertEqual(deps.judge("5.0.7", ["5.0.12", "2.1.7"], []), "5.0.12")
        self.assertIsNone(deps.judge("2.1.7", ["5.0.12", "2.1.7"], []))
        self.assertEqual(deps.judge("1.1.11", ["5.0.12", "2.1.7"], []), "2.1.7")
        self.assertIsNone(deps.judge("6.0.0", ["5.0.12"], []))
        self.assertEqual(deps.judge("0.23.36", ["0.23.45"], []), "0.23.45")
        self.assertEqual(deps.judge("0.21.12", ["0.23.45"], []), "0.23.45")  # below every target line: conservative

    def test_python_versions(self):
        k = deps.version_key
        self.assertLess(k("1.2.3rc1"), k("1.2.3"))
        self.assertLess(k("1.2.3.dev1"), k("1.2.3a1"))
        self.assertLess(k("1.2.3a1"), k("1.2.3b1"))
        self.assertLess(k("1.2.3b1"), k("1.2.3rc1"))
        self.assertLess(k("1.2.3"), k("1.2.3.post1"))
        self.assertLess(k("1.2.3.post1"), k("1.2.3.post2"))
        self.assertLess(k("1.2.3.post1.dev1"), k("1.2.3.post1"))
        self.assertEqual(k("1.2.3"), k("1.2.3.0"))
        self.assertEqual(deps.judge("1.2.3rc1", ["1.2.3"], []), "1.2.3")
        self.assertEqual(deps.judge("1.2.3.post1", ["1.2.3.post2"], []), "1.2.3.post2")

    def test_semver_prereleases_still_order(self):
        k = deps.version_key
        self.assertLess(k("1.0.0-alpha"), k("1.0.0-alpha.1"))
        self.assertLess(k("1.0.0-alpha.1"), k("1.0.0-beta"))
        self.assertLess(k("1.0.0-rc.1"), k("1.0.0"))
        self.assertLess(k("v0.0.0-20230101000000-abcdef123456"), k("v0.1.0"))
        with self.assertRaises(ValueError):
            k("latest")

    def test_range_alternatives(self):
        rng = "< 1.2.3 || >= 2.0.0, < 2.0.5"
        self.assertTrue(deps.in_range("1.0.0", rng))
        self.assertTrue(deps.in_range("2.0.1", rng))
        self.assertFalse(deps.in_range("1.5.0", rng))

    def test_range_rejects_partial_syntax(self):
        for rng in (">= 1.0.0 && < 2.0.0", ">= 1.0.0, ~2.0", ">= 1.0.0,", "< 1.2.3 | >= 2.0.0"):
            with self.subTest(rng=rng), self.assertRaises(ValueError):
                deps.in_range("1.0.0", rng)

    def test_judge_by_range(self):
        self.assertIsNone(deps.judge("0.21.12", ["0.23.45"], [">= 0.23.13, < 0.23.45"]))
        self.assertEqual(deps.judge("0.23.36", ["0.23.45"], [">= 0.23.13, < 0.23.45"]), "0.23.45")
        self.assertEqual(deps.judge("1.1.3", [], ["<= 1.1.3"]), "")


class Readers(unittest.TestCase):
    def test_cargo(self):
        root = make_repo({"Cargo.lock": CARGO_LOCK, "crates/ffi/Cargo.lock": CARGO_LOCK.replace("0.23.36", "0.23.45")})
        code, r = run(root, "--ecosystem", "rust", "--package", "rustls", "--affected", ">= 0.23.13, < 0.23.45", "--target", "0.23.45")
        self.assertEqual(code, 1)
        self.assertEqual([(lf["path"], lf["versions"]) for lf in r["lockfiles"]],
                         [("Cargo.lock", ["0.21.12", "0.23.36"]), ("crates/ffi/Cargo.lock", ["0.21.12", "0.23.45"])])
        self.assertEqual(r["vulnerable"], [{"path": "Cargo.lock", "version": "0.23.36", "needs": "0.23.45"}])

    def test_pnpm_v9_and_v6(self):
        root = make_repo({"pnpm-lock.yaml": PNPM_V9, "legacy/pnpm-lock.yaml": PNPM_V6})
        code, r = run(root, "--ecosystem", "npm", "--package", "source-map-js", "--target", "1.2.2")
        self.assertEqual(code, 1)
        self.assertEqual({lf["path"]: lf["versions"] for lf in r["lockfiles"]},
                         {"pnpm-lock.yaml": ["1.2.1"], "legacy/pnpm-lock.yaml": ["1.0.2"]})
        _, r = run(root, "--ecosystem", "npm", "--package", "left-pad")
        self.assertEqual(r["lockfiles"], [{"path": "legacy/pnpm-lock.yaml", "versions": ["1.3.0"], "vulnerable": []}])
        _, r = run(root, "--ecosystem", "npm", "--package", "next", "--target", "15.5.27")
        self.assertEqual(r["lockfiles"][0]["versions"], ["15.5.24"])

    def test_package_lock_nested(self):
        root = make_repo({"web/package-lock.json": PACKAGE_LOCK})
        code, r = run(root, "--ecosystem", "npm", "--package", "braces", "--affected", "<= 3.0.3")
        self.assertEqual(code, 1)
        self.assertEqual(r["lockfiles"][0]["versions"], ["2.3.2", "3.0.3"])
        self.assertEqual([v["needs"] for v in r["vulnerable"]], [None, None])
        _, r = run(root, "--ecosystem", "npm", "--package", "@scope/pkg")
        self.assertEqual(r["lockfiles"][0]["versions"], ["1.0.0"])

    def test_yarn_classic_and_berry(self):
        root = make_repo({"a/yarn.lock": YARN_CLASSIC, "b/yarn.lock": YARN_BERRY})
        _, r = run(root, "--ecosystem", "npm", "--package", "braces")
        self.assertEqual({lf["path"]: lf["versions"] for lf in r["lockfiles"]}, {"a/yarn.lock": ["3.0.2"], "b/yarn.lock": ["3.0.3"]})
        _, r = run(root, "--ecosystem", "npm", "--package", "@scope/braces")
        self.assertEqual(r["lockfiles"][0]["versions"], ["1.0.0"])

    def test_bun_lock(self):
        root = make_repo({"bun.lock": BUN_LOCK, "old/bun.lockb": "binary"})
        code, r = run(root, "--ecosystem", "npm", "--package", "sharp", "--target", "0.35.5")
        self.assertEqual(code, 1)
        self.assertEqual(r["lockfiles"][0]["versions"], ["0.34.5", "0.35.3"])
        self.assertEqual(r["unsupported"][0]["path"], "old/bun.lockb")

    def test_go_mod(self):
        root = make_repo({"tests/go.mod": GO_MOD})
        code, r = run(root, "--ecosystem", "go", "--package", "golang.org/x/crypto", "--target", "v0.35.0")
        self.assertEqual(code, 1)
        self.assertEqual(r["lockfiles"][0]["versions"], ["v0.31.0"])
        self.assertEqual(r["manifests"], [])  # indirect: not a direct require
        _, r = run(root, "--ecosystem", "golang", "--package", "github.com/jackc/pgx/v5", "--target", "5.9.0")
        self.assertEqual(r["manifests"], [{"path": "tests/go.mod", "field": "require", "spec": "v5.7.1"}])

    def test_python(self):
        root = make_repo({
            "tests/poetry.lock": '[[package]]\nname = "pytest"\nversion = "8.3.0"\n',
            "requirements-dev.txt": "PyTest==8.2.0  # pinned\nrequests>=2\n",
            "Pipfile.lock": {"default": {}, "develop": {"pytest": {"version": "==9.0.3"}}},
        })
        code, r = run(root, "--ecosystem", "python", "--package", "pytest", "--target", "9.0.3")
        self.assertEqual(code, 1)
        self.assertEqual({lf["path"]: lf["versions"] for lf in r["lockfiles"]},
                         {"tests/poetry.lock": ["8.3.0"], "requirements-dev.txt": ["8.2.0"], "Pipfile.lock": ["9.0.3"]})

    def test_composer(self):
        root = make_repo({"composer.lock": {"packages": [], "packages-dev": [{"name": "phpunit/phpunit", "version": "10.5.60"}]}})
        code, r = run(root, "--ecosystem", "php", "--package", "phpunit/phpunit", "--target", "10.5.62")
        self.assertEqual((code, r["vulnerable"][0]["version"]), (1, "10.5.60"))


class Scan(unittest.TestCase):
    def test_absent_package_is_ok(self):
        root = make_repo({"Cargo.lock": CARGO_LOCK})
        code, r = run(root, "--ecosystem", "rust", "--package", "hickory-resolver", "--target", "0.26.2")
        self.assertEqual((code, r["ok"], r["lockfiles"]), (0, True, []))

    def test_skips_generated_directories(self):
        root = make_repo({"node_modules/x/package-lock.json": PACKAGE_LOCK, "target/Cargo.lock": CARGO_LOCK})
        _, r = run(root, "--ecosystem", "npm", "--package", "braces")
        self.assertEqual(r["lockfiles"], [])

    def test_manifests(self):
        root = make_repo({
            "package.json": {"devDependencies": {"next": "catalog:security"}, "pnpm": {"overrides": {"sharp@<0.35": "0.35.5"}}},
            "pnpm-workspace.yaml": "catalogs:\n  security:\n    next: 15.5.24\n",
            "Cargo.toml": '[workspace.dependencies]\nrustls = { version = "0.23", default-features = false }\n\n[dependencies.hickory-resolver]\nversion = "0.26"\n',
        })
        _, r = run(root, "--ecosystem", "npm", "--package", "next")
        self.assertEqual({(m["path"], m["spec"]) for m in r["manifests"]}, {("package.json", "catalog:security"), ("pnpm-workspace.yaml", "15.5.24")})
        _, r = run(root, "--ecosystem", "npm", "--package", "sharp")
        self.assertEqual(r["manifests"][0]["field"], "pnpm.overrides[sharp@<0.35]")
        _, r = run(root, "--ecosystem", "rust", "--package", "rustls")
        self.assertEqual(r["manifests"][0]["field"], "workspace.dependencies")
        _, r = run(root, "--ecosystem", "rust", "--package", "hickory-resolver")
        self.assertEqual(r["manifests"][0]["spec"], '"0.26"')

    def test_go_mod_ignores_exclude_and_replace_sources(self):
        go_mod = ("module example.com/app\n\ngo 1.22\n\nrequire golang.org/x/net v0.20.0\n\n"
                  "exclude (\n\tgolang.org/x/net v0.1.0\n)\n\n"
                  "replace (\n\tgolang.org/x/net v0.2.0 => golang.org/x/net v0.20.0\n)\n\n"
                  "exclude golang.org/x/net v0.3.0\n"
                  "replace golang.org/x/net v0.4.0 => golang.org/x/net v0.20.0\n"
                  "retract v1.0.0\n")
        root = make_repo({"go.mod": go_mod})
        code, r = run(root, "--ecosystem", "go", "--package", "golang.org/x/net", "--target", "v0.20.0")
        self.assertEqual(r["lockfiles"][0]["versions"], ["v0.20.0"])
        self.assertEqual(r["manifests"], [{"path": "go.mod", "field": "require", "spec": "v0.20.0"}])
        self.assertEqual(code, 0)

    def assert_unreadable(self, root, name):
        with contextlib.redirect_stderr(io.StringIO()):
            code, r = run(root, "--ecosystem", "npm", "--package", "x")
        self.assertEqual(code, 2)
        self.assertFalse(r["ok"])
        self.assertIn(name, [u["path"] for u in r["unsupported"]])

    def test_broken_symlink_lockfile_is_not_vulnerable(self):
        root = make_repo({})
        (root / "package-lock.json").symlink_to(root / "missing-target.json")
        self.assert_unreadable(root, "package-lock.json")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores file permissions")
    def test_permission_denied_lockfile_is_not_vulnerable(self):
        root = make_repo({"package-lock.json": PACKAGE_LOCK})
        lock = root / "package-lock.json"
        lock.chmod(0)
        try:
            self.assert_unreadable(root, "package-lock.json")
        finally:
            lock.chmod(0o644)

    def test_malformed_lockfile_shapes_are_not_vulnerable(self):
        for files in ({"package-lock.json": {"packages": ["x"]}}, {"package-lock.json": ["x"]}):
            with self.subTest(files=files):
                self.assert_unreadable(make_repo(files), "package-lock.json")

    def test_unrecognizable_lockfile_text_is_unreadable(self):
        # G3: a lockfile the reader cannot recognize must not read as "package absent" (exit 0).
        garbage = "\x00\x01 this is not a lockfile {{{\n"
        cases = [
            ("rust", "Cargo.lock", garbage),
            ("rust", "Cargo.lock", 'version = 3\n\n[[package]]\nname = "rustls"\nversi'),  # truncated block
            ("pip", "poetry.lock", garbage),
            ("pip", "uv.lock", garbage),
            ("npm", "pnpm-lock.yaml", garbage),
            ("npm", "yarn.lock", garbage),
            ("npm", "yarn.lock", '# yarn lockfile v1\n\n"rustls@^0.23.0":\n'),  # truncated entry
            ("npm", "bun.lock", garbage),
            ("go", "go.mod", garbage),
            ("npm", "package-lock.json", "{}"),
            ("composer", "composer.lock", "{}"),
            ("pip", "Pipfile.lock", "{}"),
        ]
        for eco, name, text in cases:
            with self.subTest(file=name, text=text):
                with contextlib.redirect_stderr(io.StringIO()):
                    code, r = run(make_repo({name: text}), "--ecosystem", eco, "--package", "rustls", "--target", "0.23.45")
                self.assertEqual((code, r["ok"]), (2, False))
                self.assertIn(name, [u["path"] for u in r["unsupported"]])

    def test_valid_empty_lockfiles_read_as_zero_packages(self):
        cases = [
            ("rust", "Cargo.lock", "# This file is automatically @generated by Cargo.\n# It is not intended for manual editing.\nversion = 4\n"),
            ("pip", "poetry.lock", 'package = []\n\n[metadata]\nlock-version = "2.0"\npython-versions = "^3.11"\ncontent-hash = "x"\n'),
            ("pip", "uv.lock", 'version = 1\nrevision = 2\nrequires-python = ">=3.11"\n'),
            ("npm", "pnpm-lock.yaml", "lockfileVersion: '9.0'\n\nsettings:\n  autoInstallPeers: true\n\nimporters:\n\n  .: {}\n"),
            ("npm", "yarn.lock", "# THIS IS AN AUTOGENERATED FILE. DO NOT EDIT THIS FILE DIRECTLY.\n# yarn lockfile v1\n\n\n"),
            ("npm", "yarn.lock", "# This file is generated by running \"yarn install\" inside your project.\n\n__metadata:\n  version: 8\n  cacheKey: 10c0\n"),
            ("npm", "bun.lock", '{\n  "lockfileVersion": 1,\n  "workspaces": {\n    "": {\n      "name": "app",\n    },\n  },\n  "packages": {},\n}\n'),
            ("npm", "package-lock.json", {"name": "app", "lockfileVersion": 3, "requires": True, "packages": {"": {"name": "app"}}}),
            ("go", "go.mod", "module example.com/app\n\ngo 1.22\n"),
        ]
        for eco, name, text in cases:
            with self.subTest(file=name):
                code, r = run(make_repo({name: text}), "--ecosystem", eco, "--package", "rustls", "--target", "0.23.45")
                self.assertEqual((code, r["ok"], r["unsupported"]), (0, True, []))

    def test_toml_readers_with_and_without_tomllib(self):
        cargo = ('# This file is automatically @generated by Cargo.\nversion = 4\n\n'
                 '[[package]]\nname = "app"\nversion = "0.1.0"\ndependencies = [\n "rustls",\n "serde",\n]\n\n'
                 '[[package]]\nname = "rustls"\nversion = "0.23.36"\nsource = "registry+https://github.com/rust-lang/crates.io-index"\n'
                 'checksum = "abc"\ndependencies = [\n "ring",\n]\n')
        uv = ('version = 1\nrevision = 2\nrequires-python = ">=3.11"\n\n'
              '[[package]]\nname = "app"\nsource = { virtual = "." }\ndependencies = [\n    { name = "rustls" },\n]\n\n'
              '[package.metadata]\nrequires-dist = [{ name = "rustls", specifier = ">=0.23" }]\n\n'
              '[[package]]\nname = "rustls"\nversion = "0.23.36"\nsource = { registry = "https://pypi.org/simple" }\n'
              'sdist = { url = "https://x/rustls.tar.gz", hash = "sha256:a", size = 1 }\n'
              'wheels = [\n    { url = "https://x/rustls.whl", hash = "sha256:b", size = 2 },\n]\n')
        poetry = ('[[package]]\nname = "rustls"\nversion = "0.23.36"\ndescription = "x"\noptional = false\n'
                  'python-versions = ">=3.8"\nfiles = [\n    {file = "rustls.whl", hash = "sha256:a"},\n]\n\n'
                  '[package.dependencies]\nfoo = ">=1"\n\n[metadata]\nlock-version = "2.0"\ncontent-hash = "x"\n')
        garbage = "\x00\x01 this is not a lockfile {{{\n"
        truncated = 'version = 3\n\n[[package]]\nname = "rustls"\nversi'
        for flag in (deps.tomllib, None):
            with self.subTest(tomllib=flag is not None), mock.patch.object(deps, "tomllib", flag):
                for eco, name, text in (("rust", "Cargo.lock", cargo), ("pip", "uv.lock", uv), ("pip", "poetry.lock", poetry)):
                    code, r = run(make_repo({name: text}), "--ecosystem", eco, "--package", "rustls", "--target", "0.23.45")
                    self.assertEqual((code, r["lockfiles"][0]["versions"], r["unsupported"]), (1, ["0.23.36"], []), name)
                for text in (garbage, truncated, 'foo = "bar"\n'):
                    with contextlib.redirect_stderr(io.StringIO()):
                        code, r = run(make_repo({"Cargo.lock": text}), "--ecosystem", "rust", "--package", "rustls")
                    self.assertEqual((code, r["ok"]), (2, False), text)
                for text in ("version = 4\n", 'package = []\n\n[metadata]\nlock-version = "2.0"\n'):
                    code, r = run(make_repo({"Cargo.lock": text}), "--ecosystem", "rust", "--package", "rustls")
                    self.assertEqual((code, r["ok"]), (0, True), text)

    def test_malformed_manifest_is_reported_not_fatal(self):
        root = make_repo({"package.json": {"dependencies": ["x"]}, "pnpm-lock.yaml": PNPM_V9})
        code, r = run(root, "--ecosystem", "npm", "--package", "source-map-js", "--target", "1.2.2")
        self.assertEqual(code, 1)
        self.assertEqual(r["manifests"], [])
        self.assertIn("package.json", [u["path"] for u in r["unsupported"]])

    def test_go_replace_to_older_version_is_used(self):
        go_mod = ("module example.com/app\n\nrequire golang.org/x/net v0.20.0\n\n"
                  "replace golang.org/x/net => golang.org/x/net v0.10.0\n")
        code, r = run(make_repo({"go.mod": go_mod}), "--ecosystem", "go", "--package", "golang.org/x/net", "--target", "v0.20.0")
        self.assertEqual(r["lockfiles"][0]["versions"], ["v0.10.0"])
        self.assertEqual(code, 1)

    def test_go_replace_version_specific_and_block(self):
        go_mod = ("module example.com/app\n\nrequire golang.org/x/net v0.20.0\n\n"
                  "replace (\n\tgolang.org/x/net v0.19.0 => golang.org/x/net v0.1.0\n"
                  "\tgolang.org/x/net v0.20.0 => golang.org/x/net v0.21.0\n)\n")
        code, r = run(make_repo({"go.mod": go_mod}), "--ecosystem", "go", "--package", "golang.org/x/net", "--target", "v0.20.0")
        self.assertEqual((code, r["lockfiles"][0]["versions"]), (0, ["v0.21.0"]))

    def test_go_replace_to_fork_or_path_is_unreadable(self):
        for dest in ("../net", "github.com/fork/net v0.20.0"):
            with self.subTest(dest=dest):
                go_mod = f"module example.com/app\n\nrequire golang.org/x/net v0.20.0\n\nreplace golang.org/x/net => {dest}\n"
                root = make_repo({"go.mod": go_mod})
                with contextlib.redirect_stderr(io.StringIO()):
                    code, r = run(root, "--ecosystem", "go", "--package", "golang.org/x/net", "--target", "v0.20.0")
                self.assertEqual(code, 2)
                self.assertIn("go.mod", [u["path"] for u in r["unsupported"]])

    def test_go_replace_of_other_module_does_not_block(self):
        go_mod = ("module example.com/app\n\nrequire (\n\tgolang.org/x/net v0.20.0\n\tgolang.org/x/text v0.3.0\n)\n\n"
                  "replace golang.org/x/text => ../text\n")
        code, r = run(make_repo({"go.mod": go_mod}), "--ecosystem", "go", "--package", "golang.org/x/net", "--target", "v0.20.0")
        self.assertEqual((code, r["unsupported"]), (0, []))

    def test_npm_alias_uses_real_package_name(self):
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/demo-alias": {"name": "demo", "version": "1.0.0"}}}
        code, r = run(make_repo({"package-lock.json": lock}), "--ecosystem", "npm", "--package", "demo", "--target", "1.0.1")
        self.assertEqual((code, r["lockfiles"][0]["versions"]), (1, ["1.0.0"]))

    def test_npm_v1_alias_uses_real_package_name(self):
        lock = {"lockfileVersion": 1, "dependencies": {"demo-alias": {"version": "npm:demo@1.0.0"}}}
        code, r = run(make_repo({"package-lock.json": lock}), "--ecosystem", "npm", "--package", "demo", "--target", "1.0.1")
        self.assertEqual((code, r["lockfiles"][0]["versions"]), (1, ["1.0.0"]))

    def test_yarn_classic_alias_uses_real_package_name(self):
        lock = '# yarn lockfile v1\n\n"demo-alias@npm:demo@^1.0.0":\n  version "1.0.0"\n'
        code, r = run(make_repo({"yarn.lock": lock}), "--ecosystem", "npm", "--package", "demo", "--target", "1.0.1")
        self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["1.0.0"]]))

    def test_yarn_berry_alias_uses_real_package_name(self):
        lock = '__metadata:\n  version: 8\n\n"demo-alias@npm:demo@npm:^1.0.0":\n  version: 1.0.0\n  resolution: "demo@npm:1.0.0"\n'
        code, r = run(make_repo({"yarn.lock": lock}), "--ecosystem", "npm", "--package", "demo", "--target", "1.0.1")
        self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["1.0.0"]]))

    def test_yarn_scoped_alias_uses_real_package_name(self):
        classic = '# yarn lockfile v1\n\n"alias@npm:@scope/pkg@^1.0.0":\n  version "1.0.0"\n'
        berry = '__metadata:\n  version: 8\n\n"alias@npm:@scope/pkg@npm:^1.0.0":\n  version: 1.0.0\n'
        code, r = run(make_repo({"a/yarn.lock": classic, "b/yarn.lock": berry}),
                      "--ecosystem", "npm", "--package", "@scope/pkg", "--target", "1.0.1")
        self.assertEqual((code, {lf["path"]: lf["versions"] for lf in r["lockfiles"]}),
                         (1, {"a/yarn.lock": ["1.0.0"], "b/yarn.lock": ["1.0.0"]}))

    def test_unparseable_version_is_an_error(self):
        root = make_repo({"requirements.txt": "demo==1.2.3~weird\n"})
        with contextlib.redirect_stderr(io.StringIO()):
            code, _ = run(root, "--ecosystem", "pip", "--package", "demo", "--target", "1.2.3")
        self.assertEqual(code, 2)

    def test_bad_usage(self):
        root = make_repo({})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run(root, "--ecosystem", "cobol", "--package", "x")[0], 2)
            self.assertEqual(run(root, "--ecosystem", "npm", "--package", "x", "--affected", "nonsense")[0], 2)
            self.assertEqual(deps.main([str(root / "missing"), "--ecosystem", "npm", "--package", "x"]), 2)



def scan_code(files, eco, package, target="2.0.0"):
    """(exit code, report) for a scan of a fresh repository holding `files`."""
    with contextlib.redirect_stderr(io.StringIO()):
        return run(make_repo(files), "--ecosystem", eco, "--package", package, "--target", target)


class FailOpenRegressions(unittest.TestCase):
    """One test per reported or audited gap: each scenario returned exit 0 before the fix."""

    def assert_exit_2(self, files, eco, package):
        code, r = scan_code(files, eco, package)
        self.assertEqual((code, r and r["ok"]), (2, False), r)

    def test_h2_yarn_git_ssh_selector_keeps_package_name(self):
        lock = '# yarn lockfile v1\n\n"foo@git+ssh://git@github.com/acme/foo.git#abc123":\n  version "1.0.0"\n'
        code, r = scan_code({"yarn.lock": lock}, "npm", "foo")
        self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["1.0.0"]]))

    def test_h4_package_lock_entry_without_version_is_unreadable(self):
        lock = {"lockfileVersion": 3, "packages": {"": {}, "node_modules/foo": {"resolved": "https://r.example/foo-1.0.0.tgz"}}}
        self.assert_exit_2({"package-lock.json": lock}, "npm", "foo")

    def test_r1a_yarn_selectors_that_hide_the_name(self):
        y1, yb = "# yarn lockfile v1\n\n", "__metadata:\n  version: 8\n\n"
        found = [  # the real package is recovered at its recorded version
            (y1 + '"@s/foo@https://r.example/@s/foo/-/foo-1.0.0.tgz":\n  version "1.0.0"\n', "@s/foo"),
            (yb + '"foo@git@github.com:acme/foo.git#commit=abc":\n  version: 1.0.0\n', "foo"),
            (yb + '"foo@patch:foo@npm%3A^1.0.0#~builtin<compat/foo>":\n  version: 1.0.0\n', "foo"),
        ]
        for lock, pkg in found:
            with self.subTest(lock=lock):
                code, r = scan_code({"yarn.lock": lock}, "npm", pkg)
                self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["1.0.0"]]))
        for header in ("foo:", '"^1.0.0":', '"!!foo@^1.0.0":'):  # no recoverable name: never silently dropped
            with self.subTest(header=header):
                self.assert_exit_2({"yarn.lock": f'{y1}{header}\n  version "1.0.0"\n'}, "npm", "foo")

    def test_r1b_package_lock_shapes_that_drop_an_entry(self):
        for packages in ({"node_modules/foo": "1.0.0"}, {"node_modules/": {"version": "1.0.0"}}):
            with self.subTest(packages=packages):
                self.assert_exit_2({"package-lock.json": {"lockfileVersion": 3, "packages": {"": {}, **packages}}}, "npm", "foo")
        with self.subTest(lockfile="v1 dependency without version"):
            self.assert_exit_2({"package-lock.json": {"lockfileVersion": 1, "dependencies": {"foo": {"resolved": "x"}}}}, "npm", "foo")
        # A non-string version crashed with a traceback (exit 1, "vulnerable") instead of reporting the file unreadable.
        root = make_repo({"package-lock.json": {"lockfileVersion": 3, "packages": {"": {}, "node_modules/foo": {"version": 1}}}})
        proc = subprocess.run([sys.executable, str(Path(deps.__file__)), str(root), "--ecosystem", "npm", "--package", "foo"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)

    def test_r1c_pnpm_non_registry_and_garbled_keys(self):
        head = "lockfileVersion: '9.0'\n\npackages:\n"
        for body in ("  foo@https://codeload.github.com/acme/foo/tar.gz/abc:\n    resolution: {tarball: https://x}\n    version: 1.0.0\n",
                     "  foo@git+https://github.com/acme/foo.git#abc:\n    resolution: {commit: abc, repo: x, type: git}\n    version: 1.0.0\n"):
            with self.subTest(body=body):
                code, r = scan_code({"pnpm-lock.yaml": head + body}, "npm", "foo")
                self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["1.0.0"]]))
        v6 = "lockfileVersion: '6.0'\n\npackages:\n  github.com/acme/foo/abc:\n    resolution: {tarball: x}\n    name: foo\n    version: 1.0.0\n"
        with self.subTest(body="v6 host path key"):
            code, r = scan_code({"pnpm-lock.yaml": v6}, "npm", "foo")
            self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["1.0.0"]]))
        for key in ("foo@", "f#o@1.0.0", "!!foo@1.0.0"):
            with self.subTest(key=key):
                self.assert_exit_2({"pnpm-lock.yaml": f"{head}  {key}:\n    resolution: {{integrity: x}}\n"}, "npm", "foo")

    def test_r1d_bun_entries_without_a_semver(self):
        for entry in ('["foo@github:acme/foo#abc", {}, "acme-foo-abc"]', '["foo@https://r.example/foo-1.0.0.tgz", {}]',
                      '["foo", {}]', '"foo@1.0.0"', '["!!foo@1.0.0", "", {}, "sha"]'):
            with self.subTest(entry=entry):
                self.assert_exit_2({"bun.lock": f'{{"lockfileVersion": 1, "packages": {{"foo": {entry}}}}}'}, "npm", "foo")

    def test_r1e_toml_lockfiles_reject_invalid_names(self):
        for flag in (deps.tomllib, None):
            for eco, name in (("rust", "Cargo.lock"), ("pip", "poetry.lock"), ("pip", "uv.lock")):
                with self.subTest(tomllib=flag is not None, file=name), mock.patch.object(deps, "tomllib", flag):
                    lock = 'version = 3\n\n[[package]]\nname = "!!foo"\nversion = "1.0.0"\n'
                    self.assert_exit_2({name: lock}, eco, "foo")

    def test_r1f_pipfile_lock_entries_without_a_pin(self):
        for meta in ({"git": "https://github.com/acme/foo.git", "ref": "abc"}, {"version": "*"},
                     {"file": "https://r.example/foo-1.0.0.tar.gz"}, {"hashes": ["sha256:a"]}):
            with self.subTest(meta=meta):
                self.assert_exit_2({"Pipfile.lock": {"_meta": {}, "default": {"foo": meta}, "develop": {}}}, "pip", "foo")

    def test_r1g_requirements_lines_without_a_pin(self):
        for line in ("foo>=1.0", "foo", "foo @ https://r.example/foo-1.0.0.tar.gz",
                     "-e git+https://github.com/acme/foo.git@abc#egg=foo", "!!foo==1.0.0"):
            with self.subTest(line=line):
                self.assert_exit_2({"requirements.txt": line + "\n"}, "pip", "foo")
        code, _ = scan_code({"requirements.txt": "# autogenerated by pip-compile\n-e .\n-r requirements-dev.txt\n"
                                                 "--index-url https://x\n# c\n\n",
                             "requirements-dev.txt": "# autogenerated by pip-compile\n"}, "pip", "foo")
        self.assertEqual(code, 0)  # option, include, local-editable and comment lines are not entries

    def test_r1h_composer_entries_missing_name_or_version(self):
        for packages in ([{"name": "acme/foo"}], [{"version": "1.0.0"}], {"acme/foo": {"name": "acme/foo", "version": "1.0.0"}},
                         [{"name": "!!acme/foo", "version": "1.0.0"}]):
            with self.subTest(packages=packages):
                self.assert_exit_2({"composer.lock": {"content-hash": "x", "packages": packages}}, "composer", "acme/foo")

    def test_r1i_go_mod_requires_that_are_dropped(self):
        head = "module example.com/app\n\ngo 1.22\n\n"
        for body, mod in (('require (\n\t"github.com/acme/foo" v1.0.0\n)\n', "github.com/acme/foo"),
                          ("require example/foo v1.0.0\n", "example/foo")):
            with self.subTest(body=body):
                code, r = scan_code({"go.mod": head + body}, "go", mod)
                self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["v1.0.0"]]))
        for body in ("require (\n\tgithub.com/acme/foo\n)\n", "require (\n\t!!github.com/acme/foo v1.0.0\n)\n"):
            with self.subTest(body=body):
                self.assert_exit_2({"go.mod": head + body}, "go", "github.com/acme/foo")
        with self.subTest(body="quoted replace"):  # a replace the reader cannot parse must not leave the require in force
            body = 'require github.com/acme/foo v2.0.0\n\nreplace "github.com/acme/foo" => "github.com/acme/foo" v1.0.0\n'
            code, r = scan_code({"go.mod": head + body}, "go", "github.com/acme/foo")
            self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]]), (1, [["v1.0.0"]]))

    def test_r1j_go_mod_before_1_17_does_not_prove_absence(self):
        # Before go 1.17, go.mod lists only direct requirements; a transitive module may be resolved without appearing.
        for directive in ("go 1.16\n\n", ""):
            with self.subTest(directive=directive):
                go_mod = f"module example.com/app\n\n{directive}require github.com/acme/bar v1.0.0\n"
                self.assert_exit_2({"go.mod": go_mod}, "go", "github.com/acme/foo")


# ---------------------------------------------------------------- reader contract harness
#
# Each format lists entry templates: template(name, version) renders one entry, and version=None renders
# the same entry with its version removed. `entries` are third-party installs with a recorded version;
# `versionless` are third-party installs whose format records no version (scanning them must exit 2);
# `exempt` are first-party entries that legitimately carry no version and must not make the file unreadable.

GARBLE = "!!"  # a prefix that is invalid in every supported ecosystem's package-name grammar


def _drop(d, key):
    return {k: v for k, v in d.items() if k != key}


def _npm3(path, **extra):
    def t(name, version):
        key = path.format(name=name)
        meta = dict(extra, **({"version": version} if version is not None else {}))
        return key, meta
    return t


def _npm3_alias(name, version):
    return "node_modules/alias-x", {"name": name, **({"version": version} if version is not None else {})}


def _render_npm3(frags):
    return json.dumps({"name": "app", "lockfileVersion": 3, "requires": True,
                       "packages": {"": {"name": "app", "workspaces": ["packages/*"]}, **dict(frags)}})


def _npm1(name, version):
    return name, {"version": version, "resolved": f"https://r.example/{name}.tgz", "integrity": "sha512-a"} if version else {"resolved": "x"}


def _npm1_nested(name, version):
    return "parent", {"version": "9.0.0", "dependencies": dict([_npm1(name, version)])}


def _npm1_alias(name, version):
    return "alias-x", {"version": f"npm:{name}@{version}"} if version else {"version": f"npm:{name}"}


def _render_npm1(frags):
    return json.dumps({"name": "app", "lockfileVersion": 1, "requires": True, "dependencies": dict(frags)})


def _pnpm9(key_fmt, body="    resolution: {{integrity: sha512-a}}\n", snapshot=None):
    def t(name, version):
        ref = f"@{version}" if version is not None else ""
        key = key_fmt.format(name=name, ref=ref)
        snap = (snapshot or key_fmt).format(name=name, ref=ref)
        return f"  {key}:\n{body.format(name=name, version=version)}", f"  {snap}: {{}}\n"
    return t


def _pnpm9_url(url):
    def t(name, version):
        key = f"{name}@{url.format(name=name)}"
        ver = f"    version: {version}\n" if version is not None else ""
        return f"  {key}:\n    resolution: {{tarball: {url.format(name=name)}}}\n{ver}", f"  {key}: {{}}\n"
    return t


def _render_pnpm9(frags):
    return ("lockfileVersion: '9.0'\n\nimporters:\n\n  .:\n    dependencies: {}\n\npackages:\n\n"
            + "\n".join(p for p, _ in frags) + "\nsnapshots:\n\n" + "\n".join(s for _, s in frags))


def _pnpm6(key_fmt):
    def t(name, version):
        # Without a version the key keeps only "/name": dropping just the version from "/name/1.0.0_peer@1"
        # would leave "/name_peer@1", a different and valid package key rather than a versionless one.
        key = key_fmt.format(name=name, version=version) if version is not None else "/" + name
        return f"  {key}:\n    resolution: {{integrity: sha512-a}}\n    dev: false\n"
    return t


def _pnpm6_git(name, version):
    ver = f"    version: {version}\n" if version is not None else ""
    return f"  github.com/acme/{name.lstrip('!')}/abc123:\n    resolution: {{tarball: https://codeload.github.com/x}}\n    name: {name}\n{ver}    dev: false\n"


def _render_pnpm6(frags):
    return "lockfileVersion: '6.0'\n\npackages:\n\n" + "\n".join(frags)


def _yarn1(selectors):
    def t(name, version):
        header = ", ".join(s.format(name=name) for s in selectors)
        ver = f'  version "{version}"\n' if version is not None else ""
        return f"{header}:\n{ver}  resolved \"https://r.example/x.tgz#abc\"\n  integrity sha512-a\n"
    return t


def _render_yarn1(frags):
    return "# THIS IS AN AUTOGENERATED FILE. DO NOT EDIT THIS FILE DIRECTLY.\n# yarn lockfile v1\n\n\n" + "\n".join(frags)


def _berry(selectors, resolution):
    def t(name, version):
        header = ", ".join(s.format(name=name) for s in selectors)
        ver = f"  version: {version}\n" if version is not None else ""
        return (f'"{header}":\n{ver}  resolution: "{resolution.format(name=name, version=version)}"\n'
                f"  checksum: 10c0/abc\n  languageName: node\n  linkType: hard\n")
    return t


def _render_berry(frags):
    return "# This file is generated by running \"yarn install\" inside your project.\n\n__metadata:\n  version: 8\n  cacheKey: 10c0\n\n" + "\n".join(frags)


def _bun(key, ref=None):
    def t(name, version):
        spec = f"{name}@{ref.format(name=name) if ref else (version if version is not None else '')}"
        return f'    "{key.format(name=name)}": ["{spec}", "", {{}}, "sha512-a"],\n'
    return t


def _render_bun(frags):
    return ('{\n  "lockfileVersion": 1,\n  "workspaces": {\n    "": {\n      "name": "app",\n    },\n  },\n'
            '  "packages": {\n' + "".join(frags) + "  }\n}\n")


def _toml(extra=""):
    def t(name, version):
        ver = f'version = "{version}"\n' if version is not None else ""
        return f'[[package]]\nname = "{name}"\n{ver}{extra}'
    return t


def _render_cargo(frags):
    return "# This file is automatically @generated by Cargo.\n# It is not intended for manual editing.\nversion = 4\n\n" + "\n".join(frags)


def _render_poetry(frags):
    return "\n".join(frags) + '\n[metadata]\nlock-version = "2.1"\npython-versions = "^3.11"\ncontent-hash = "abc"\n'


def _render_uv(frags):
    return 'version = 1\nrevision = 2\nrequires-python = ">=3.11"\n\n' + "\n".join(frags)


def _render_pdm(frags):
    return ('# This file is @generated by PDM.\n# It is not intended for manual editing.\n\n[metadata]\ngroups = ["default"]\n'
            'strategy = ["inherit_metadata"]\nlock_version = "4.5.0"\ncontent_hash = "sha256:abc"\n\n' + "\n".join(frags))


def _pylock(extra=""):
    def t(name, version):
        ver = f'version = "{version}"\n' if version is not None else ""
        return f'[[packages]]\nname = "{name}"\n{ver}{extra}'
    return t


def _render_pylock(frags):
    return 'lock-version = "1.0"\nenvironments = ["sys_platform == \'linux\'"]\nrequires-python = ">=3.11"\ncreated-by = "uv"\n\n' + "\n".join(frags)


def _deno(fmt="{name}@{version}"):
    def t(name, version):
        key = fmt.format(name=name, version=version) if version is not None else name
        return key, {"integrity": "sha512-a", "dependencies": []}
    return t


def _render_deno4(frags):
    return json.dumps({"version": "4", "specifiers": {"jsr:@std/assert@1": "1.0.19"},
                       "jsr": {"@std/assert@1.0.19": {"integrity": "x"}}, "npm": dict(frags)})


def _render_deno3(frags):
    return json.dumps({"version": "3", "packages": {"specifiers": {}, "jsr": {}, "npm": dict(frags)}, "remote": {}})


def _pipfile(section, **extra):
    def t(name, version):
        return section, name, dict(extra, **({"version": f"=={version}"} if version is not None else {}))
    return t


def _render_pipfile(frags):
    data = {"_meta": {"hash": {"sha256": "abc"}, "pipfile-spec": 6, "requires": {}, "sources": []}, "default": {}, "develop": {}}
    for section, name, meta in frags:
        data[section][name] = meta
    return json.dumps(data)


def _req(fmt):
    def t(name, version):
        return fmt.format(name=name, pin=f"=={version}" if version is not None else "")
    return t


def _render_requirements(frags):
    return "# pinned\n--index-url https://pypi.org/simple\n--prefer-binary\n\n" + "\n".join(frags) + "\n"


def _composer(section):
    def t(name, version):
        return section, {"name": name, **({"version": version} if version is not None else {}),
                         "source": {"type": "git", "url": "https://x", "reference": "abc"}, "type": "library"}
    return t


def _render_composer(frags):
    data = {"content-hash": "abc", "packages": [], "packages-dev": []}
    for section, pkg in frags:
        data[section].append(pkg)
    return json.dumps(data)


def _go(fmt):
    def t(name, version):
        return fmt.format(name=name, ver=f" {version}" if version is not None else "")
    return t


def _render_go(frags):
    block = [f for f in frags if f.startswith("\t")]
    single = [f for f in frags if not f.startswith("\t")]
    return "module example.com/app\n\ngo 1.22\n\nrequire (\n" + "\n".join(block) + "\n)\n\n" + "\n".join(single) + "\n"


NPM3_ENTRIES = [
    ("plain", "plain", "1.0.0", _npm3("node_modules/{name}", resolved="https://r.example/plain.tgz", integrity="sha512-a")),
    ("scoped", "@scope/pkg", "1.1.0", _npm3("node_modules/{name}")),
    ("nested", "nested", "1.2.0", _npm3("node_modules/parent/node_modules/{name}")),
    ("alias", "real-alias", "1.3.0", _npm3_alias),
    ("inBundle", "bundled", "1.4.0", _npm3("node_modules/parent/node_modules/{name}", inBundle=True)),
    ("extraneous", "extra", "1.5.0", _npm3("node_modules/{name}", extraneous=True, dev=True)),
    ("git", "gitdep", "1.6.0", _npm3("node_modules/{name}", resolved="git+ssh://git@github.com/acme/gitdep.git#abc")),
    ("optional platform", "platform", "1.7.0", _npm3("node_modules/{name}", optional=True, os=["darwin"])),
    ("workspace-local install", "wsdep", "1.8.0", _npm3("packages/ws/node_modules/{name}")),
]
NPM3_EXEMPT = [("node_modules/ws", {"resolved": "packages/ws", "link": True}), ("packages/ws", {"name": "ws", "version": "0.0.1"})]

FORMATS = [
    # (label, file, eco, render, entries, versionless, exempt)
    ("package-lock v3", "package-lock.json", "npm", _render_npm3, NPM3_ENTRIES, [], NPM3_EXEMPT),
    ("npm-shrinkwrap v3", "npm-shrinkwrap.json", "npm", _render_npm3, NPM3_ENTRIES, [], NPM3_EXEMPT),
    ("package-lock v1", "package-lock.json", "npm", _render_npm1, [
        ("plain", "plain", "1.0.0", _npm1), ("scoped", "@scope/pkg", "1.1.0", _npm1),
        ("nested", "nested", "1.2.0", _npm1_nested), ("alias", "real-alias", "1.3.0", _npm1_alias),
    ], [], [("local", {"version": "file:packages/local"})]),
    ("pnpm v9", "pnpm-lock.yaml", "npm", _render_pnpm9, [
        ("plain", "plain", "1.0.0", _pnpm9("{name}{ref}")),
        ("scoped", "@scope/pkg", "1.1.0", _pnpm9("'{name}{ref}'")),
        ("peer suffix", "peer", "1.2.0", _pnpm9("{name}{ref}", snapshot="{name}{ref}(react@18.3.1)")),
        ("git", "gitdep", "1.6.0", _pnpm9_url("git+https://github.com/acme/{name}.git#abc")),
        ("tarball", "tarball", "1.7.0", _pnpm9_url("https://codeload.github.com/acme/{name}/tar.gz/abc")),
    ], [], [("  local@file:packages/local:\n    resolution: {directory: packages/local, type: directory}\n",
             "  local@file:packages/local: {}\n")]),
    ("pnpm v6", "pnpm-lock.yaml", "npm", _render_pnpm6, [
        ("plain", "plain", "1.0.0", _pnpm6("/{name}@{version}")),
        ("scoped", "@scope/pkg", "1.1.0", _pnpm6("/{name}@{version}")),
        ("peer suffix", "peer", "1.2.0", _pnpm6("/{name}@{version}(react@18.3.1)")),
        ("v5 slash", "legacy", "1.3.0", _pnpm6("/{name}/{version}")),
        ("v5 peer suffix", "peer5", "1.4.0", _pnpm6("/{name}/{version}_react@18.3.1")),
        ("git", "gitdep", "1.6.0", _pnpm6_git),
    ], [], []),
    ("yarn classic", "yarn.lock", "npm", _render_yarn1, [
        ("multi selector", "plain", "1.0.0", _yarn1(["{name}@^1.0.0", "{name}@~1.0.0"])),
        ("quoted range", "ranged", "1.0.5", _yarn1(['"{name}@>=1.0.0 <2"', '"{name}@^1.0.1"'])),
        ("scoped", "@scope/pkg", "1.1.0", _yarn1(['"{name}@^1.1.0"'])),
        ("alias", "real-alias", "1.3.0", _yarn1(['"alias-x@npm:{name}@^1.3.0"'])),
        ("git+ssh", "gitdep", "1.6.0", _yarn1(['"{name}@git+ssh://git@github.com/acme/gitdep.git#abc"'])),
        ("github", "ghdep", "1.6.1", _yarn1(['"{name}@github:acme/ghdep#abc"'])),
        ("scoped tarball", "@scope/tarball", "1.7.0", _yarn1(['"{name}@https://r.example/{name}/-/tarball-1.7.0.tgz"'])),
    ], [], []),
    ("yarn berry", "yarn.lock", "npm", _render_berry, [
        ("multi selector", "plain", "1.0.0", _berry(["{name}@npm:^1.0.0", "{name}@npm:~1.0.0"], "{name}@npm:{version}")),
        ("scoped", "@scope/pkg", "1.1.0", _berry(["{name}@npm:^1.1.0"], "{name}@npm:{version}")),
        ("alias", "real-alias", "1.3.0", _berry(["alias-x@npm:{name}@npm:^1.3.0"], "{name}@npm:{version}")),
        ("git", "gitdep", "1.6.0", _berry(["{name}@git+ssh://git@github.com/acme/gitdep.git#commit=abc"],
                                           "{name}@git+ssh://git@github.com/acme/gitdep.git#commit=abc")),
        ("github https", "ghdep", "1.6.1", _berry(["{name}@https://github.com/acme/ghdep.git#commit=abc"],
                                                  "{name}@https://github.com/acme/ghdep.git#commit=abc")),
        ("scoped tarball", "@scope/tarball", "1.7.0", _berry(["{name}@https://r.example/{name}/-/tarball-1.7.0.tgz"],
                                                             "{name}@https://r.example/{name}/-/tarball-1.7.0.tgz")),
        ("patch", "patched", "1.8.0", _berry(["{name}@patch:{name}@npm%3A^1.8.0#~builtin<compat/patched>"],
                                             "{name}@patch:{name}@npm%3A{version}#~builtin<compat/patched>::version={version}")),
    ], [], [
        f'"{sel}":\n  version: 0.0.0-use.local\n  resolution: "{sel}"\n  languageName: unknown\n  linkType: soft\n'
        for sel in ("app@workspace:.", "linked@link:../linked::locator=app%40workspace%3A.",
                    "portaled@portal:../portaled::locator=app%40workspace%3A.")
    ]),
    ("bun.lock", "bun.lock", "npm", _render_bun, [
        ("plain", "plain", "1.0.0", _bun("{name}")),
        ("scoped", "@scope/pkg", "1.1.0", _bun("{name}")),
        ("nested", "nested", "1.2.0", _bun("parent/{name}")),
        ("alias", "real-alias", "1.3.0", _bun("alias-x")),
    ], [
        ("github", "gitdep", _bun("{name}", ref="github:acme/gitdep#abc")),
        ("tarball", "tarball", _bun("{name}", ref="https://r.example/tarball-1.7.0.tgz")),
    ], [
        '    "app": ["app@workspace:packages/app"],\n',
        '    "local": ["local@file:../local", {}],\n',
        '    "linked": ["linked@link:../linked", {}],\n',
    ]),
    ("Cargo.lock", "Cargo.lock", "rust", _render_cargo, [
        ("registry", "plain", "1.0.0", _toml('source = "registry+https://github.com/rust-lang/crates.io-index"\nchecksum = "abc"\n')),
        ("git", "gitdep", "1.6.0", _toml('source = "git+https://github.com/acme/gitdep?rev=abc#abc"\n')),
        ("path member", "member", "0.1.0", _toml('dependencies = [\n "plain",\n]\n')),
    ], [], []),
    ("poetry.lock", "poetry.lock", "pip", _render_poetry, [
        ("registry", "plain", "1.0.0", _toml('description = "x"\noptional = false\npython-versions = ">=3.8"\n'
                                             'files = [\n    {file = "plain.whl", hash = "sha256:a"},\n]\n\n'
                                             '[package.dependencies]\nother = ">=1"\n\n[package.extras]\nx = ["other"]\n')),
        ("git", "gitdep", "1.6.0", _toml('description = "x"\noptional = false\npython-versions = "*"\nfiles = []\n\n'
                                         '[package.source]\ntype = "git"\nurl = "https://github.com/acme/gitdep.git"\n'
                                         'reference = "HEAD"\nresolved_reference = "abc"\n')),
    ], [], []),
    ("uv.lock", "uv.lock", "pip", _render_uv, [
        ("registry", "plain", "1.0.0", _toml('source = { registry = "https://pypi.org/simple" }\n'
                                             'sdist = { url = "https://x/plain.tar.gz", hash = "sha256:a", size = 1 }\n'
                                             'wheels = [\n    { url = "https://x/plain.whl", hash = "sha256:b", size = 2 },\n]\n')),
        ("git", "gitdep", "1.6.0", _toml('source = { git = "https://github.com/acme/gitdep?rev=abc#abc" }\n')),
    ], [], [
        '[[package]]\nname = "app"\nsource = { virtual = "." }\ndependencies = [\n    { name = "plain" },\n]\n\n'
        '[package.metadata]\nrequires-dist = [{ name = "plain", specifier = ">=1" }]\n',
        '[[package]]\nname = "member"\nsource = { editable = "packages/member" }\n',
    ]),
    ("pdm.lock", "pdm.lock", "pip", _render_pdm, [
        ("registry", "plain", "1.0.0", _toml('requires_python = ">=3.8"\nsummary = "x"\ngroups = ["default"]\n'
                                             'files = [\n    {file = "plain-1.0.0.whl", hash = "sha256:a"},\n]\n')),
        ("git", "gitdep", "1.6.0", _toml('git = "https://github.com/acme/gitdep.git"\nrevision = "abc"\n'
                                         'summary = "x"\ngroups = ["default"]\n')),
        ("dependencies", "deps", "1.2.0", _toml('summary = "x"\ndependencies = [\n    "plain>=1",\n]\n')),
    ], [], []),
    ("pylock.toml", "pylock.toml", "pip", _render_pylock, [
        ("wheels", "plain", "1.0.0", _pylock('index = "https://pypi.org/simple"\n\n[[packages.wheels]]\n'
                                              'name = "plain-1.0.0-py3-none-any.whl"\nurl = "https://x/plain.whl"\n'
                                              'hashes = {sha256 = "a"}\n')),
        ("sdist", "sdisted", "1.1.0", _pylock('index = "https://pypi.org/simple"\n\n[packages.sdist]\n'
                                               'name = "sdisted-1.1.0.tar.gz"\nurl = "https://x/s.tar.gz"\nhashes = {sha256 = "b"}\n')),
        ("marker", "marked", "1.2.0", _pylock('marker = "python_version >= \'3.8\'"\n'
                                               'wheels = [{ url = "https://x/m.whl", hashes = { sha256 = "c" } }]\n')),
    ], [
        ("vcs", "gitdep", _pylock('\n[packages.vcs]\ntype = "git"\nurl = "https://github.com/acme/gitdep.git"\ncommit-id = "abc"\n')),
        ("archive", "tarball", _pylock('archive = { url = "https://r.example/tarball-1.7.0.tar.gz", hashes = { sha256 = "d" } }\n')),
    ], ['[[packages]]\nname = "app"\ndirectory = { path = ".", editable = true }\n']),
    ("deno.lock v4", "deno.lock", "npm", _render_deno4, [
        ("plain", "plain", "1.0.0", _deno()),
        ("scoped", "@scope/pkg", "1.1.0", _deno()),
        ("peer suffix", "peer", "1.2.0", _deno("{name}@{version}_react@18.3.1")),
    ], [], []),
    ("deno.lock v3", "deno.lock", "npm", _render_deno3, [
        ("plain", "plain", "1.0.0", _deno()),
        ("scoped", "@scope/pkg", "1.1.0", _deno()),
    ], [], []),
    ("Pipfile.lock", "Pipfile.lock", "pip", _render_pipfile, [
        ("default", "plain", "1.0.0", _pipfile("default", hashes=["sha256:a"], index="pypi")),
        ("markers", "marked", "1.1.0", _pipfile("default", markers="python_version >= '3.8'")),
        ("extras", "extraed", "1.2.0", _pipfile("default", extras=["socks"])),
        ("develop", "devdep", "1.3.0", _pipfile("develop")),
    ], [
        ("git", "gitdep", lambda n, v: ("default", n, {"git": "https://github.com/acme/gitdep.git", "ref": "abc"})),
        ("file", "tarball", lambda n, v: ("default", n, {"file": "https://r.example/tarball-1.7.0.tar.gz"})),
    ], [("default", "app", {"editable": True, "path": "."})]),
    ("requirements.txt", "requirements.txt", "pip", _render_requirements, [
        ("pin", "plain", "1.0.0", _req("{name}{pin}")),
        ("extras and marker", "extraed", "1.1.0", _req('{name}[socks]{pin} ; python_version >= "3.8"')),
        ("hashes", "hashed", "1.2.0", _req("{name}{pin} \\\n    --hash=sha256:abc")),
        ("comment", "commented", "1.3.0", _req("{name}{pin}  # via plain")),
    ], [
        ("unpinned", "loose", lambda n, v: f"{n}>=1.0"),
        ("url", "urlpkg", lambda n, v: f"{n} @ https://r.example/{n}-1.0.0.tar.gz"),
        ("editable vcs", "gitdep", lambda n, v: f"-e git+https://github.com/acme/gitdep.git@abc#egg={n}"),
    ], ["-e ."]),
    ("composer.lock", "composer.lock", "composer", _render_composer, [
        ("packages", "acme/plain", "1.0.0", _composer("packages")),
        ("v prefix", "acme/vpref", "v1.1.0", _composer("packages")),
        ("packages-dev", "acme/devdep", "1.3.0", _composer("packages-dev")),
    ], [], []),
    ("go.mod", "go.mod", "go", _render_go, [
        ("block", "github.com/acme/plain", "v1.0.0", _go("\t{name}{ver}")),
        ("indirect", "golang.org/x/indirect", "v0.1.0", _go("\t{name}{ver} // indirect")),
        ("major suffix", "github.com/acme/major/v2", "v2.3.0", _go("\t{name}{ver}")),
        ("gopkg.in", "gopkg.in/yaml.v3", "v3.0.1", _go("\t{name}{ver}")),
        ("pseudo-version", "github.com/acme/pseudo", "v0.0.0-20230101000000-abcdef123456", _go("\t{name}{ver}")),
        ("incompatible", "github.com/acme/incompat", "v2.0.0+incompatible", _go("\t{name}{ver}")),
        ("single line", "github.com/acme/single", "v1.2.0", _go("require {name}{ver}")),
    ], [], []),
]


class ReaderContract(unittest.TestCase):
    """Every entry a reader sees yields its real name and version, or the scan exits 2 — never a silent drop."""

    @staticmethod
    def cases():
        for label, fname, eco, render, entries, versionless, exempt in FORMATS:
            toml = fname in ("Cargo.lock", "poetry.lock", "uv.lock", "pdm.lock", "pylock.toml")
            for flag in (deps.tomllib, None) if toml else (deps.tomllib,):
                fmt = f"{label} (tomllib={flag is not None})" if toml else label
                yield fmt, flag, fname, eco, render, entries, versionless, exempt

    @staticmethod
    def fixture(render, entries, exempt, extra=(), mutate=None):
        """Render `entries` (plus `extra` versionless (label, name, template) entries) with one optional mutation."""
        frags = []
        for i, (_, name, version, t) in enumerate(list(entries) + [(lb, n, None, t) for lb, n, t in extra]):
            if mutate and mutate[0] == i:
                name, version = (GARBLE + name, version) if mutate[1] == "garble" else (name, None)
            frags.append(t(name, version))
        return render(frags + list(exempt))

    def scan(self, flag, fname, text, eco, name):
        with mock.patch.object(deps, "tomllib", flag):
            return scan_code({fname: text}, eco, name, target="99.0.0")

    # Versionless third-party entries are rendered in a fixture of their own, so these tests hold whether the fix
    # reports such an entry as unreadable for the whole file or only for a scan of that package.

    def test_completeness(self):
        """(a) every third-party entry in a realistic fixture is found under its real name at its recorded version."""
        for fmt, flag, fname, eco, render, entries, versionless, exempt in self.cases():
            text = self.fixture(render, entries, exempt)
            for label, name, version, _ in entries:
                with self.subTest(format=fmt, entry=label):
                    _, r = self.scan(flag, fname, text, eco, name)
                    self.assertEqual(([lf["versions"] for lf in r["lockfiles"]], r["unsupported"]), ([[version]], []))
            for label, name, t in versionless:
                with self.subTest(format=fmt, entry=f"versionless {label}"):
                    text = self.fixture(render, entries, exempt, extra=[(label, name, t)])
                    code, r = self.scan(flag, fname, text, eco, name)
                    self.assertEqual((code, r["ok"]), (2, False))

    def test_exemptions_do_not_block(self):
        """First-party versionless entries (links, workspaces, virtual or editable members) leave the file readable."""
        for fmt, flag, fname, eco, render, entries, versionless, exempt in self.cases():
            if exempt:
                with self.subTest(format=fmt):
                    _, name, version, _ = entries[0]
                    code, r = self.scan(flag, fname, self.fixture(render, entries, exempt), eco, name)
                    self.assertEqual((code, [lf["versions"] for lf in r["lockfiles"]], r["unsupported"]), (1, [[version]], []))

    def test_fail_closed(self):
        """(b) garbling the name of, or removing the version from, any single third-party entry exits 2, never 0."""
        for fmt, flag, fname, eco, render, entries, versionless, exempt in self.cases():
            for i, (label, name, _, _) in enumerate(entries):
                for kind in ("garble", "drop-version"):
                    with self.subTest(format=fmt, entry=label, mutation=kind):
                        text = self.fixture(render, entries, exempt, mutate=(i, kind))
                        code, _ = self.scan(flag, fname, text, eco, name)
                        self.assertEqual(code, 2, text)
            for label, name, t in versionless:
                with self.subTest(format=fmt, entry=f"versionless {label}", mutation="garble"):
                    text = self.fixture(render, entries, exempt, extra=[(label, name, t)], mutate=(len(entries), "garble"))
                    code, _ = self.scan(flag, fname, text, eco, name)
                    self.assertEqual(code, 2, text)


# ---------------------------------------------------------------- coverage contract
#
# The reader contract covers each file the scan reads. Coverage is the other half of "exit 0 proves safety": every
# file that determines the package's resolved versions must be read. Each fixture below places the package's only
# resolved version (1.0.0, below the 2.0.0 target) behind one inclusion, workspace or discovery mechanism. The scan
# must find it (exit 1) or say it cannot prove safety (exit 2); exit 0 means it certified a file it never read.

GO_FIXED = "module example.com/app\n\ngo 1.21\n\nrequire github.com/acme/foo v2.0.0\n"
PDM_LOCK = '[metadata]\ngroups = ["default"]\nlock_version = "4.4.1"\ncontent_hash = "sha256:x"\n\n' \
           '[[package]]\nname = "foo"\nversion = "1.0.0"\nrequires_python = ">=3.8"\nsummary = "x"\n'
PYLOCK = 'lock-version = "1.0"\ncreated-by = "uv"\n\n[[packages]]\nname = "foo"\nversion = "1.0.0"\n'
DENO_V3 = {"version": "3", "packages": {"specifiers": {"npm:foo@^1": "npm:foo@1.0.0"},
                                        "npm": {"foo@1.0.0": {"integrity": "sha512-x", "dependencies": {}}}}}
DENO_V4 = {"version": "4", "specifiers": {"npm:foo@^1": "1.0.0"}, "npm": {"foo@1.0.0": {"integrity": "sha512-x"}}}

# (entry, mechanism, ecosystem, package, files, scan subdirectory or None)
COVERAGE = {
    "J2": [
        ("requirements -r to a file outside the requirements*.txt glob", "pip", "foo",
         {"requirements.txt": "-r deps/prod.txt\n", "deps/prod.txt": "foo==1.0.0\n"}, None),
    ],
    "R5a": [
        ("--requirement=PATH", "pip", "foo",
         {"requirements.txt": "--requirement=deps/prod.txt\n", "deps/prod.txt": "foo==1.0.0\n"}, None),
        ("--requirement PATH", "pip", "foo",
         {"requirements.txt": "--requirement deps/prod.txt\n", "deps/prod.txt": "foo==1.0.0\n"}, None),
        ("-rPATH (no space)", "pip", "foo",
         {"requirements.txt": "-rdeps/prod.txt\n", "deps/prod.txt": "foo==1.0.0\n"}, None),
        ("-c constraints pin a transitive package", "pip", "foo",
         {"requirements.txt": "bar==1.0.0\n-c deps/pins.txt\n", "deps/pins.txt": "foo==1.0.0\n"}, None),
        ("--constraint PATH", "pip", "foo",
         {"requirements.txt": "bar==1.0.0\n--constraint deps/pins.txt\n", "deps/pins.txt": "foo==1.0.0\n"}, None),
        ("nested include, relative to the including file", "pip", "foo",
         {"requirements.txt": "-r a/one.txt\n", "a/one.txt": "-r ../b/two.txt\n", "b/two.txt": "foo==1.0.0\n"}, None),
        ("include cycle", "pip", "foo",
         {"requirements.txt": "-r deps/a.txt\n", "deps/a.txt": "-r ../requirements.txt\nfoo==1.0.0\n"}, None),
        ("include of a missing file", "pip", "foo", {"requirements.txt": "-r deps/missing.txt\n"}, None),
        ("include of a URL", "pip", "foo", {"requirements.txt": "-r https://example.com/prod.txt\n"}, None),
        ("include outside the scanned repository", "pip", "foo",
         {"repo/requirements.txt": "-r ../shared/prod.txt\n", "shared/prod.txt": "foo==1.0.0\n"}, "repo"),
    ],
    "R5b": [
        ("requirements/ directory of .txt files", "pip", "foo", {"requirements/prod.txt": "foo==1.0.0\n"}, None),
        ("constraints.txt", "pip", "foo", {"requirements.txt": "bar==1.0.0\n", "constraints.txt": "foo==1.0.0\n"}, None),
        ("rye requirements.lock", "pip", "foo", {"requirements.lock": "-e file:.\nfoo==1.0.0\n"}, None),
        ("rye requirements-dev.lock", "pip", "foo", {"requirements-dev.lock": "foo==1.0.0\n"}, None),
    ],
    "R5c": [
        ("pdm.lock", "pip", "foo", {"pdm.lock": PDM_LOCK}, None),
        ("pylock.toml (PEP 751)", "pip", "foo", {"pylock.toml": PYLOCK}, None),
        ("pylock.<name>.toml (PEP 751)", "pip", "foo", {"pylock.prod.toml": PYLOCK}, None),
        ("deno.lock v3 npm packages", "npm", "foo", {"deno.lock": DENO_V3}, None),
        ("deno.lock v4 npm packages", "npm", "foo", {"deno.lock": DENO_V4}, None),
    ],
    "R5d": [
        ("binary bun.lockb, the repository's only lockfile", "npm", "foo",
         {"package.json": {"dependencies": {"foo": "^1.0.0"}}, "bun.lockb": "\x00bun-lockfile-binary"}, None),
    ],
    "R5e": [
        ("go.work replace overrides the go.mod version", "go", "github.com/acme/foo",
         {"go.mod": GO_FIXED,
          "go.work": "go 1.21\n\nuse .\n\nreplace github.com/acme/foo v2.0.0 => github.com/acme/foo v1.0.0\n"}, None),
        ("go.work replace to a local fork", "go", "github.com/acme/foo",
         {"go.mod": GO_FIXED, "go.work": "go 1.21\n\nuse .\n\nreplace github.com/acme/foo => ./forks/foo\n"}, None),
        ("go.work uses a module outside the scanned repository", "go", "github.com/acme/foo",
         {"repo/go.mod": "module example.com/app\n\ngo 1.21\n", "repo/go.work": "go 1.21\n\nuse (\n\t.\n\t../other\n)\n",
          "other/go.mod": "module example.com/other\n\ngo 1.21\n\nrequire github.com/acme/foo v1.0.0\n"}, "repo"),
    ],
}


PKG_LOCK_FOO = {"lockfileVersion": 3, "packages": {"": {"name": "app"}, "node_modules/foo": {"version": "1.0.0"}}}
PKG_LOCK_BAR = {"lockfileVersion": 3, "packages": {"": {"name": "app"}, "node_modules/bar": {"version": "1.0.0"}}}
GIT = shutil.which("git")

COVERAGE.update({
    # R5f fixtures run in a git work tree (the trailing True), where discovery follows git rather than directory names.
    "R5f": [
        ("lockfile under a directory named build", "npm", "foo",
         {"packages/build/package.json": {"dependencies": {"foo": "1.0.0"}},
          "packages/build/package-lock.json": PKG_LOCK_FOO}, None, True),
        ("lockfile under a hidden directory", "npm", "foo",
         {".devcontainer/package.json": {"dependencies": {"foo": "1.0.0"}},
          ".devcontainer/package-lock.json": PKG_LOCK_FOO}, None, True),
    ],
    "R5g": [
        ("package.json with no lockfile", "npm", "foo", {"package.json": {"dependencies": {"foo": "1.0.0"}}}, None),
        ("nested package.json with no lockfile above it", "npm", "foo",
         {"tools/x/package.json": {"devDependencies": {"foo": "^1.0.0"}}}, None),
        ("Cargo.toml with no Cargo.lock", "rust", "foo",
         {"Cargo.toml": '[package]\nname = "app"\nversion = "0.1.0"\n\n[dependencies]\nfoo = "1.0.0"\n'}, None),
        ("composer.json with no composer.lock", "composer", "acme/foo",
         {"composer.json": {"require": {"acme/foo": "1.0.0"}}}, None),
        ("pyproject [project] dependencies with no lockfile", "pip", "foo",
         {"pyproject.toml": '[project]\nname = "app"\ndependencies = [\n  "Foo[extra]>=1.0",\n]\n'}, None),
        ("pyproject poetry dependencies with no lockfile", "pip", "foo",
         {"pyproject.toml": '[tool.poetry]\nname = "app"\n\n[tool.poetry.dependencies]\npython = "^3.11"\nfoo = "^1.0"\n'}, None),
        ("Pipfile with no Pipfile.lock", "pip", "foo", {"Pipfile": '[packages]\nfoo = "==1.0.0"\n'}, None),
    ],
    "R5h": [
        ("hand-written pins list only top-level packages", "pip", "urllib3",
         {"requirements.txt": "requests==2.31.0\n"}, None),
        ("unpinned requirements", "pip", "urllib3", {"requirements.txt": "requests>=2\n"}, None),
        ("compiled header but an unpinned line", "pip", "urllib3",
         {"requirements.txt": "# This file is autogenerated by pip-compile with Python 3.12\n"
                              "requests==2.31.0\n    # via -r requirements.in\nidna>=3\n"}, None),
        ("hash on only some requirements", "pip", "urllib3",
         {"requirements.txt": "requests==2.31.0 --hash=sha256:abc\nidna==3.7\n"}, None),
    ],
})


def coverage_scan(files, eco, package, subdir=None, git=False):
    root = make_repo(files)
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    with contextlib.redirect_stderr(io.StringIO()):
        return run(root / subdir if subdir else root, "--ecosystem", eco, "--package", package, "--target", "2.0.0")


class CoverageContract(unittest.TestCase):
    """A file that resolves the package and is never read must not count as proof of absence: exit 1 or 2, never 0."""

    def assert_covered(self, entry):
        for mechanism, eco, package, files, subdir, *git in COVERAGE[entry]:
            with self.subTest(entry=entry, mechanism=mechanism):
                if git and not GIT:
                    self.skipTest("git is not installed")
                code, r = coverage_scan(files, eco, package, subdir, bool(git))
                self.assertIn(code, (1, 2), f"exit 0 certified {package} absent; report: {r}")
                self.assertFalse(r["ok"], r)

    def test_j2_requirements_include(self):
        self.assert_covered("J2")

    def test_r5a_requirements_include_forms(self):
        self.assert_covered("R5a")

    def test_r5b_requirements_files_outside_the_glob(self):
        self.assert_covered("R5b")

    def test_r5c_lockfile_formats_never_discovered(self):
        self.assert_covered("R5c")

    def test_r5d_unsupported_lockfile_blocks_certification(self):
        self.assert_covered("R5d")

    def test_r5e_go_work(self):
        self.assert_covered("R5e")

    def test_r5f_lockfiles_in_skipped_directories(self):
        self.assert_covered("R5f")

    def test_r5g_manifest_without_a_lockfile(self):
        self.assert_covered("R5g")

    def test_r5g_python_manifests_without_tomllib(self):
        with mock.patch.object(deps, "tomllib", None):
            for mechanism, eco, package, files, subdir in COVERAGE["R5g"]:
                if eco == "pip":
                    with self.subTest(mechanism=mechanism):
                        code, r = coverage_scan(files, eco, package, subdir)
                        self.assertEqual((code, len(r["manifests"])), (2, 1), r)

    def test_r5h_requirements_that_are_not_a_complete_lock(self):
        self.assert_covered("R5h")

    def test_followed_mechanisms_do_not_block_a_clean_scan(self):
        """Guards against over-correction: a mechanism the scan can follow, with nothing vulnerable behind it, exits 0."""
        compiled = "    # via -r requirements.in\n"
        for mechanism, eco, package, files, *git in [
            ("requirements include of a clean compiled file", "pip", "foo",
             {"requirements.txt": f"-r deps/base.txt\nbar==1.0.0\n{compiled}", "deps/base.txt": f"baz==1.0.0\n{compiled}"}),
            ("requirements compiled by pip-compile (header)", "pip", "foo",
             {"requirements.txt": "#\n# This file is autogenerated by pip-compile with Python 3.12\n#\nbar==1.0.0\n"}),
            ("requirements exported by uv (header)", "pip", "foo",
             {"requirements.txt": "# This file was autogenerated by uv via the following command:\n"
                                  "#    uv export --frozen\nbar==1.0.0\n"}),
            ("requirements with --hash on every line", "pip", "foo",
             {"requirements.txt": "bar==1.0.0 \\\n    --hash=sha256:abc\nbaz==1.0.0 --hash=sha256:def\n"}),
            ("hand-written constraints file", "pip", "foo",
             {"requirements.txt": f"bar==1.0.0\n{compiled}-c constraints.txt\n", "constraints.txt": "baz==1.0.0\n"}),
            ("deno.lock with only jsr packages", "npm", "foo",
             {"deno.lock": {"version": "5", "specifiers": {"jsr:@std/assert@1": "1.0.19"},
                            "jsr": {"@std/assert@1.0.19": {"integrity": "x"}}}}),
            ("go.work using only in-repo modules", "go", "github.com/acme/foo",
             {"go.mod": GO_FIXED, "go.work": "go 1.21\n\nuse .\n"}),
            ("nested manifest covered by an ancestor lockfile", "npm", "foo",
             {"package-lock.json": PKG_LOCK_BAR, "tools/x/package.json": {"dependencies": {"foo": "1.0.0"}}}),
            ("manifest without a lockfile that does not name the package", "npm", "foo",
             {"package.json": {"dependencies": {"bar": "1.0.0"}}}),
            ("git: ignored directory is not read", "npm", "foo",
             {".gitignore": "out/\n", "package-lock.json": PKG_LOCK_BAR, "out/package-lock.json": PKG_LOCK_FOO}, True),
            ("git: node_modules is excluded even when not ignored", "npm", "foo",
             {"package-lock.json": PKG_LOCK_BAR, "node_modules/x/package-lock.json": PKG_LOCK_FOO}, True),
        ]:
            with self.subTest(mechanism=mechanism):
                if git and not GIT:
                    self.skipTest("git is not installed")
                code, r = coverage_scan(files, eco, package, git=bool(git))
                self.assertEqual((code, r["unsupported"]), (0, []), r)
                self.assertEqual(r.get("discovery"), "git" if git else "walk", r)


if __name__ == "__main__":
    unittest.main()
