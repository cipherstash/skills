"""Tests for scripts/deps.py. Run: python3 -m unittest discover -s tests (from the skill directory)."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
