import carb.settings
import carb.tokens
import omni.kit.app
import omni.kit.test


class TestConfig(omni.kit.test.AsyncTestCase):
    async def test_l1_public_release_configuration(self):
        settings = carb.settings.get_settings()
        app_version = settings.get("/app/version")

        # This test covers a moment in time when we switch version to RC.
        # Following test cases must be satisfied.
        is_rc = "-rc." in app_version
        # title_format_string = settings.get("exts/omni.kit.window.modifier.titlebar/titleFormatString")

        # if is_rc:
            # Make sure the title format string doesn't use app version if app version contains rc
            # title_using_app_version = "/app/version" in title_format_string
            # self.assertFalse(is_rc and title_using_app_version, "check failed: title format string contains app version which contains 'rc'")

            # Make sure the title format string has "Beta" in it
            # title_has_beta = "Beta" in title_format_string
            # self.assertTrue(title_has_beta, "check failed: title format string does not have 'Beta  ' in it")

        # if is_rc:
        #     Make sure the title format string doesn't use app version if app version contains rc
        #     title_using_app_version = "/app/version" in title_format_string
        #     self.assertFalse(is_rc and title_using_app_version, "check failed: title format string contains app version which contains 'rc'")

        #     Make sure the title format string has "Beta" in it
        #     title_has_beta = "Beta" in title_format_string
        #     self.assertTrue(title_has_beta, "check failed: title format string does not have 'Beta  ' in it")

        # Make sure we set build to external when going into RC release mode
        # external = settings.get("/privacy/externalBuild") or False
        # self.assertEqual(
        #     external,
        #     is_rc,
        #     "check failed: is this an RC build? %s Is /privacy/externalBuild set to true? %s" % (is_rc, external),
        # )

        # if is_rc:
        #     # Make sure we remove some extensions from public release
        #     EXTENSIONS = [
        #         # "omni.kit.profiler.tracy",
        #         "omni.kit.window.jira",
        #         "omni.kit.testing.services",
        #         "omni.kit.tests.usd_stress",
        #         "omni.kit.tests.basic_validation",
        #         # "omni.kit.extension.reports",
        #     ]

        #     manager = omni.kit.app.get_app().get_extension_manager()
        #     ext_names = {e["name"] for e in manager.get_extensions()}

        #     for ext in EXTENSIONS:
        #         self.assertEqual(
        #             ext in ext_names,
        #             False,
        #             f"looks like {ext} was not removed from public build",
        #         )

    async def test_l1_usd_explorer_and_usd_explorer_full_have_same_version(self):
        manager = omni.kit.app.get_app().get_extension_manager()

        EXTENSIONS = [
            "omni.usd_explorer",
            "omni.usd_explorer.full",
        ]

        # need to find both extensions and they need the same version id
        usd_explorer_exts = [e for e in manager.get_extensions() if e.get("name", "") in EXTENSIONS]
        self.assertEqual(len(usd_explorer_exts), 2)
        self.assertEqual(
            usd_explorer_exts[0]["version"],
            usd_explorer_exts[1]["version"],
            "omni.usd_explorer.kit and omni.usd_explorer.full.kit have different versions",
        )
