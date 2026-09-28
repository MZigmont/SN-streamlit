import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from httplib2 import Response
from googleapiclient.errors import HttpError
import google_drive_interface as drive
import app_context


class Stopped(BaseException):
    pass


class DriveAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.st = Mock()
        self.st.user.tokens = {"access": "first-user-token"}
        self.st.session_state = {}
        self.st.button.return_value = False
        self.st.stop.side_effect = Stopped
        self.st.rerun.side_effect = Stopped
        for name, value in [("st", self.st), ("require_admin", Mock()), ("build", Mock())]:
            patcher = patch.object(drive, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_service_uses_each_current_users_token(self):
        app_context.get_drive_service()
        first = drive.build.call_args.kwargs["credentials"]
        self.st.user.tokens = {"access": "second-user-token"}
        app_context.get_drive_service()
        second = drive.build.call_args.kwargs["credentials"]
        self.assertEqual(first.token, "first-user-token")
        self.assertEqual(second.token, "second-user-token")
        self.assertEqual(drive.require_admin.call_count, 2)

    def test_denied_admin_never_builds_client(self):
        drive.require_admin.side_effect = Stopped
        with self.assertRaises(Stopped):
            drive.google_drive_auth()
        drive.build.assert_not_called()

    def test_missing_token_offers_browser_login(self):
        self.st.user.tokens = {}
        self.st.button.return_value = True
        with self.assertRaises(Stopped):
            drive.google_drive_auth()
        self.st.login.assert_called_once_with("google")
        drive.build.assert_not_called()

    def test_expired_token_reconnect_persists_until_new_token(self):
        error = HttpError(Response({"status": "401"}), b"{}")
        with self.assertRaises(Stopped):
            drive._handle_drive_error(error, "upload")
        with self.assertRaises(Stopped):
            drive.google_drive_auth()
        drive.build.assert_not_called()
        self.st.user.tokens = {"access": "renewed-token"}
        drive.google_drive_auth()
        self.assertNotIn("expired_drive_token", self.st.session_state)
        drive.build.assert_called_once()

    def test_failed_download_preserves_database_and_removes_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "test.db"
            database.write_bytes(b"original database")
            with patch.object(drive, "MediaIoBaseDownload") as downloader:
                downloader.return_value.next_chunk.side_effect = HttpError(Response({"status": "401"}), b"{}")
                with self.assertRaises(Stopped):
                    drive.download_db_file(Mock(), "file-id", database)
            self.assertEqual(database.read_bytes(), b"original database")
            self.assertEqual(list(Path(directory).iterdir()), [database])

    def test_successful_download_replaces_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "test.db"
            database.write_bytes(b"old")
            def downloader(handle, request):
                handle.write(b"new")
                return Mock(next_chunk=Mock(return_value=(None, True)))
            with patch.object(drive, "MediaIoBaseDownload", side_effect=downloader):
                drive.download_db_file(Mock(), "file-id", database)
            self.assertEqual(database.read_bytes(), b"new")

    def test_forbidden_does_not_log_tokens_or_force_login(self):
        error = HttpError(Response({"status": "403"}), b"sensitive details")
        drive._handle_drive_error(error, "upload")
        self.st.error.assert_called_once()
        self.assertNotIn("sensitive details", self.st.error.call_args.args[0])
        self.st.rerun.assert_not_called()


if __name__ == "__main__":
    unittest.main()
