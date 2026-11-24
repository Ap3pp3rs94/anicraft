#!/usr/bin/env python3
"""Synthetic tests for the one Nightly launcher every Linux nightly format installs.

No app build: a recorder stands in for the real program, so each layout is exercised exactly as
packaging/linux/{package.sh,flatpak-bundle.sh,nightly-arch-tar.sh,nightly.sh} installs it.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINUX = HERE / "linux"
LAUNCHER = LINUX / "nightly-launch.sh"
RECORDER = '#!/bin/sh\nfor arg in "$@"; do printf \'%s\\n\' "$arg"; done\n'


class Layout(unittest.TestCase):
    """Each format's install layout, run through the shared launcher."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name).resolve()
        self.home = self.root / "home with space"
        self.home.mkdir()

    # -- building the five layouts ------------------------------------------------------------
    def script(self, path, text=RECORDER):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)
        return path

    def launcher(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LAUNCHER, path)
        path.chmod(0o755)
        return path

    def layouts(self):
        made = {}
        base = self.root / "layouts"
        # deb/rpm: /usr/bin/anicraft-nightly runs /usr/lib/anicraft-nightly/anicraft
        prefix = base / "usr"
        made["deb-rpm"] = (
            self.launcher(prefix / "bin/anicraft-nightly"),
            self.script(prefix / "lib/anicraft-nightly/anicraft"),
        )
        # AppImage: AppRun at the AppDir root runs usr/bin/anicraft
        appdir = base / "AniCraft.AppDir"
        made["appimage"] = (self.launcher(appdir / "AppRun"), self.script(appdir / "usr/bin/anicraft"))
        # Arch handoff: bin/anicraft runs bin/.anicraft-nightly/anicraft
        arch = base / "arch"
        made["arch"] = (self.launcher(arch / "bin/anicraft"), self.script(arch / "bin/.anicraft-nightly/anicraft"))
        # Flatpak: /app/bin/anicraft-nightly runs /app/bin/anicraft
        flatpak = base / "app"
        made["flatpak"] = (self.launcher(flatpak / "bin/anicraft-nightly"), self.script(flatpak / "bin/anicraft"))
        # nightly tar: anicraft-nightly runs the anicraft beside it
        tar = base / "tar"
        made["tar"] = (self.launcher(tar / "anicraft-nightly"), self.script(tar / "anicraft"))
        return made

    def run_launcher(self, command, *arguments, env=None, cwd=None):
        environment = {"PATH": "/usr/bin:/bin", "HOME": str(self.home)}
        environment.update(env or {})
        return subprocess.run(
            [str(command), *arguments], capture_output=True, text=True, timeout=30,
            env=None if environment is None else {k: v for k, v in environment.items() if v is not None},
            cwd=str(cwd or self.root),
        )

    def profile(self, data_home=None):
        return str(Path(data_home or self.home / ".local/share") / "anicraft-nightly/profile")

    def protocol(self, *files, data_home=None):
        return ["--launch-profile", "nightly-v1", "--profile-root", self.profile(data_home), "--", *files]

    def arguments(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    # -- the contract every format shares -----------------------------------------------------
    def test_every_format_starts_the_real_program_in_the_nightlys_own_profile(self):
        files = ["scene with spaces.anicraft", "--other-name.anicraft"]
        for name, (command, _) in self.layouts().items():
            with self.subTest(layout=name):
                self.assertEqual(self.arguments(self.run_launcher(command, *files)), self.protocol(*files))

    def test_a_co_installed_stable_program_is_never_used(self):
        # deb/rpm: /usr/bin/anicraft is stable's program, so the launcher must take the packaged
        # nightly one from /usr/lib even though a same-named file sits beside it.
        self.layouts()
        prefix = self.root / "layouts/usr"
        stable = prefix / "bin/anicraft"
        stable.write_text(RECORDER.replace("for arg", "# the stable program must never run\nfor arg"))
        stable.chmod(0o755)
        result = self.run_launcher(prefix / "bin/anicraft-nightly", "walk.anicraft")
        self.assertEqual(self.arguments(result), self.protocol("walk.anicraft"))
        self.assertNotIn("stable", result.stdout)

    def test_the_profile_follows_xdg_data_home(self):
        data_home = self.root / "xdg with space"
        for name, (command, _) in self.layouts().items():
            with self.subTest(layout=name):
                result = self.run_launcher(command, "walk.anicraft", env={"XDG_DATA_HOME": str(data_home)})
                self.assertEqual(self.arguments(result), self.protocol("walk.anicraft", data_home=data_home))

    def test_a_version_query_answers_the_launchers_own_form(self):
        for name, (command, _) in self.layouts().items():
            for flag in ("--version", "-V"):
                with self.subTest(layout=name, flag=flag):
                    expected = ["--launch-profile", "nightly-v1", "--profile-root", self.profile(), flag]
                    self.assertEqual(self.arguments(self.run_launcher(command, flag)), expected)

    def test_a_file_named_like_a_flag_is_still_a_file(self):
        for name, (command, _) in self.layouts().items():
            with self.subTest(layout=name):
                files = ["--version", "--launch-profile", "nightly-v1"]
                self.assertEqual(self.arguments(self.run_launcher(command, *files)), self.protocol(*files))

    def test_no_arguments_is_a_bare_delimiter(self):
        for name, (command, _) in self.layouts().items():
            with self.subTest(layout=name):
                self.assertEqual(self.arguments(self.run_launcher(command)), self.protocol())

    def test_the_launcher_works_when_it_is_found_on_path(self):
        self.layouts()
        arch = self.root / "layouts/arch/bin"
        # The Arch packager installs the handoff's bin/anicraft as anicraft-nightly (or keeps it).
        (arch / "anicraft").rename(arch / "anicraft-nightly")
        result = subprocess.run(
            ["sh", "-c", 'exec anicraft-nightly "$1"', "sh", "walk.anicraft"],
            capture_output=True, text=True, timeout=30,
            env={"PATH": f"{arch}:/usr/bin:/bin", "HOME": str(self.home)},
        )
        self.assertEqual(self.arguments(result), self.protocol("walk.anicraft"))

    def test_a_missing_or_symlinked_program_is_refused_without_recursing(self):
        layouts = self.layouts()
        for name, (command, program) in layouts.items():
            with self.subTest(layout=name, case="missing"):
                moved = program.with_name(program.name + ".moved")
                program.rename(moved)
                try:
                    result = self.run_launcher(command, "walk.anicraft")
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("not where this launcher was installed", result.stderr)
                    self.assertEqual(result.stdout, "")
                finally:
                    moved.rename(program)
                with self.subTest(layout=name, case="symlink"):
                    program.unlink()
                    program.symlink_to(self.root / "elsewhere")
                    try:
                        result = self.run_launcher(command, "walk.anicraft")
                        self.assertEqual(result.returncode, 2)
                        self.assertIn("not where this launcher was installed", result.stderr)
                    finally:
                        program.unlink()
                        program.write_text(RECORDER)
                        program.chmod(0o755)

    def test_home_is_required_before_anything_runs(self):
        for name, (command, _) in self.layouts().items():
            with self.subTest(layout=name):
                result = self.run_launcher(command, "walk.anicraft", env={"HOME": None})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("HOME", result.stderr)

    def test_the_profile_never_sits_in_or_above_stables_folders(self):
        profile = Path(self.profile())
        parts = profile.parts
        self.assertEqual(parts[-2:], ("anicraft-nightly", "profile"))
        for stable in (".config", ".cache", ".local/state"):
            self.assertNotIn(str(self.home / stable / "anicraft"), str(profile))


class InstallContract(unittest.TestCase):
    """Every Linux format must install the one launcher, not its own copy of the protocol."""

    def read(self, name):
        return (LINUX / name).read_text()

    def test_every_format_installs_the_shared_launcher(self):
        package = self.read("package.sh")
        # deb/rpm GUI command and the AppImage AppRun
        self.assertIn('install -Dm755 "$HERE/nightly-launch.sh" "$NFPM_STAGE/usr/bin/$NFPM_BIN"', package)
        self.assertIn('install -Dm755 "$HERE/nightly-launch.sh" "$APPDIR/AppRun"', package)
        self.assertNotIn("<<'WRAPPER'", package)
        self.assertIn('install -Dm755 "$HERE/nightly-launch.sh" "$WORK/stage/bin/anicraft-nightly"', self.read("flatpak-bundle.sh"))
        self.assertIn('cp "$here/nightly-launch.sh" "$stage/bin/anicraft"', self.read("nightly-arch-tar.sh"))
        self.assertIn('install -m755 "$ROOT/packaging/linux/nightly-launch.sh" "$STAGE/anicraft-nightly"', self.read("nightly.sh"))
        self.assertFalse((LINUX / "nightly-arch-launch.sh").exists(), "the Arch launcher is the shared one now")

    def test_no_format_still_moves_the_settings_folder_through_the_environment(self):
        for name in ("flatpak-bundle.sh", "nightly-arch-tar.sh", "nightly.sh", "nightly-launch.sh"):
            with self.subTest(file=name):
                self.assertNotIn("XDG_CONFIG_HOME", self.read(name))
        # package.sh keeps it only for the headless CLI, which has no profile protocol (the GUI
        # command and AppRun are the launcher).
        package = self.read("package.sh")
        self.assertEqual(package.count("XDG_CONFIG_HOME"), 1)
        self.assertGreater(package.index("XDG_CONFIG_HOME"), package.index("<<'CLI_WRAPPER'"))

    def test_the_nightly_launcher_passes_the_flavors_protocol(self):
        launcher = LAUNCHER.read_text()
        self.assertIn('exec "$real_bin" --launch-profile nightly-v1 --profile-root "$profile_root" -- "$@"', launcher)
        self.assertIn('"$real_bin" --launch-profile nightly-v1 --profile-root "$profile_root" "$1"', launcher)

    def test_the_formats_that_ship_a_desktop_entry_point_it_at_the_launcher(self):
        package = self.read("package.sh")
        self.assertIn("Exec=$NFPM_BIN\\1", package)
        self.assertRegex(package, r"StartupWMClass=ai\.storyteller\.anicraft\.nightly-v1")
        flatpak = self.read("flatpak-bundle.sh")
        self.assertIn("Exec=anicraft-nightly", flatpak)
        self.assertIn("s|^command: anicraft$|command: anicraft-nightly|", flatpak)
        arch = self.read("nightly-arch-tar.sh")
        self.assertIn("Exec=anicraft-nightly", arch)
        self.assertIn("StartupWMClass=$nightly_id", arch)

    def test_nightly_metadata_declares_no_file_associations(self):
        for name in ("package.sh", "flatpak-bundle.sh", "nightly-arch-tar.sh"):
            with self.subTest(file=name):
                self.assertIn("/<mediatype>/d", self.read(name))

    def test_the_nightly_build_uses_the_apps_default_features(self):
        common = (HERE / "nightly-common.sh").read_text()
        # `-p anicraft` with its default features is the GUI a stable build ships (sound output and
        # the GPU stage); a --features/--no-default-features here would ship a different app.
        self.assertIn("cargo build --release --locked -p anicraft --target", common)
        self.assertNotIn("--no-default-features", common)
        self.assertNotIn("--features", common)

    def test_the_prepared_identity_reaches_build_rs(self):
        common = (HERE / "nightly-common.sh").read_text()
        self.assertIn("export ANICRAFT_BUILD_CHANNEL ANICRAFT_VERSION ANICRAFT_BUILD_SHA ANICRAFT_BUILD_DATE", common)
        self.assertNotIn("OVERRIDE_VERSION", common)

    def test_every_platform_checks_the_line_the_flavor_prints(self):
        expected = 'AniCraft Nightly $VERSION (nightly-v1)'
        self.assertIn(f'"{expected}"', (HERE / "nightly-common.sh").read_text())
        self.assertIn(f'"{expected}"', (HERE / "linux/nightly.sh").read_text())
        self.assertIn('"AniCraft Nightly $VERSION (nightly-v1)"', (HERE / "macos/nightly-verify.sh").read_text())
        self.assertIn("AniCraft Nightly $ExpectedVersion (nightly-v1)", (HERE / "windows/nightly.ps1").read_text())
        workflow = (HERE.parent / ".github/workflows/nightly-builds.yml").read_text()
        self.assertIn('"AniCraft Nightly $ANICRAFT_VERSION (nightly-v1)"', workflow)
        self.assertIn('"AniCraft Nightly $env:ANICRAFT_VERSION (nightly-v1)"', workflow)

    def test_the_expected_line_is_the_one_the_flavor_composes(self):
        root = HERE.parent
        self.assertIn('LaunchIdentity::NightlyV1 => tr_noop!("AniCraft Nightly")', (root / "src/platform.rs").read_text())
        self.assertIn('BuildFlavor::NightlyV1 => format!("{stable} (nightly-v1)")', (root / "src/build_flavor.rs").read_text())
        self.assertIn(
            '"{} {}", platform::name_for(platform::LaunchIdentity::NightlyV1), version_line()',
            (root / "src/main.rs").read_text(),
        )

    def test_the_window_class_is_the_desktop_entry_class(self):
        platform = (HERE.parent / "src/platform.rs").read_text()
        match = re.search(r'pub const APP_ID_NIGHTLY: &str = "([^"]+)";', platform)
        self.assertIsNotNone(match)
        nightly_id = match[1]
        self.assertEqual(nightly_id, "ai.storyteller.anicraft.nightly-v1")
        for name in ("package.sh", "flatpak-bundle.sh"):
            with self.subTest(file=name):
                self.assertIn(nightly_id, self.read(name))
        # the Arch handoff builds the same id from the stable one it rewrites.
        arch = self.read("nightly-arch-tar.sh")
        self.assertIn("app_id=ai.storyteller.anicraft", arch)
        self.assertIn("nightly_id=$app_id.nightly-v1", arch)
        self.assertIn("StartupWMClass=$nightly_id", arch)


if __name__ == "__main__":
    unittest.main()
