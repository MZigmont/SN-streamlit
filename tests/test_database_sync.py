import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app_context as ctx
import database_sync as sync
import google_drive_interface as drive


class DatabaseSyncTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "donations.db"
        self.db.write_bytes(b"original")

    def test_changes_persist_until_synced(self):
        self.assertTrue(sync.has_unsynced_changes(self.db))
        sync.mark_synced(self.db)
        self.assertFalse(sync.has_unsynced_changes(self.db))
        self.db.write_bytes(b"edited")
        self.assertTrue(sync.has_unsynced_changes(self.db))
        sync.mark_synced(self.db)
        self.assertFalse(sync.has_unsynced_changes(self.db))

    def test_failed_upload_keeps_warning_success_clears_it(self):
        sync.mark_synced(self.db)
        self.db.write_bytes(b"edited")
        service = Mock()
        request = service.files.return_value.update.return_value
        with patch.object(drive, "st"), patch.object(drive, "MediaFileUpload"):
            request.execute.side_effect = RuntimeError("offline")
            drive.upload_db_file(service, "file-id", self.db)
            self.assertTrue(sync.has_unsynced_changes(self.db))
            request.execute.side_effect = None
            drive.upload_db_file(service, "file-id", self.db)
            self.assertFalse(sync.has_unsynced_changes(self.db))

    def test_warning_updates_in_same_run_even_on_early_exit(self):
        sync.mark_synced(self.db)
        st = Mock()
        st.session_state = {"selected_db_file": str(self.db)}
        with patch.object(ctx, "st", st), patch.object(ctx, "DB_DIR", str(self.db.parent)):
            with self.assertRaises(RuntimeError):
                with ctx.database_change_warning():
                    st.empty.return_value.warning.assert_not_called()
                    self.db.write_bytes(b"edited")
                    raise RuntimeError("stop")
        self.assertIn("Make sure you sync before you leave", st.empty.return_value.warning.call_args.args[0])

    def test_download_closes_connection_before_replacing_database(self):
        st = Mock()
        st.session_state = {"selected_db_file": str(self.db)}
        st.sidebar.button.return_value = True
        conn = Mock()

        def download(*args):
            conn.close.assert_called_once()

        with patch.object(ctx, "st", st), patch.object(ctx, "get_drive_service"), patch.object(
            ctx, "download_db_file", side_effect=download
        ) as transfer:
            self.assertTrue(ctx.render_drive_sidebar(conn))
        transfer.assert_called_once()

    def test_download_status_write_failure_is_not_a_download_failure(self):
        def downloader(handle, request):
            handle.write(b"downloaded")
            return Mock(next_chunk=Mock(return_value=(None, True)))

        with patch.object(drive, "st") as st, patch.object(
            drive, "MediaIoBaseDownload", side_effect=downloader
        ), patch.object(drive, "mark_synced", side_effect=PermissionError):
            drive.download_db_file(Mock(), "file-id", self.db)
        self.assertEqual(self.db.read_bytes(), b"downloaded")
        st.error.assert_not_called()
        st.success.assert_called_once()
        self.assertIn("sync status could not be saved", st.warning.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
