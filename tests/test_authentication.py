import ast
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import authentication


class Stopped(Exception):
    pass


class User(dict):
    is_logged_in = True


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.st = Mock()
        self.st.secrets = {"access": {"approved_emails": [" Admin@example.com "]}}
        self.st.user = User(
            email="admin@EXAMPLE.com", email_verified=True,
            iss="https://accounts.google.com",
        )
        self.st.stop.side_effect = Stopped
        self.st.button.return_value = False
        self.st.sidebar.button.return_value = False
        patcher = patch.object(authentication, "st", self.st)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_approved_verified_google_user_has_access(self):
        authentication.require_admin()
        self.st.stop.assert_not_called()
        self.st.sidebar.caption.assert_called_once()

    def test_unapproved_unverified_and_wrong_issuer_are_blocked(self):
        for claim, value in [("email", "outsider@example.com"),
                             ("email_verified", False), ("email_verified", "true"),
                             ("iss", "https://other.example.com"), ("email", None)]:
            with self.subTest(claim=claim, value=value):
                original = self.st.user[claim]
                self.st.user[claim] = value
                with self.assertRaises(Stopped):
                    authentication.require_admin()
                self.st.user[claim] = original
        self.st.sidebar.caption.assert_not_called()

    def test_missing_empty_and_malformed_approval_configuration_blocks_access(self):
        for approved in [None, [], "admin@example.com", [None], [""]]:
            self.st.secrets = {"access": {"approved_emails": approved}}
            with self.assertRaises(Stopped):
                authentication.require_admin()

    def test_signed_out_login_uses_google_and_stops_page(self):
        self.st.user.is_logged_in = False
        self.st.button.return_value = True
        with self.assertRaises(Stopped):
            authentication.require_admin()
        self.st.login.assert_called_once_with("google")
        self.st.sidebar.caption.assert_not_called()

    def test_approval_is_rechecked_on_next_run(self):
        authentication.require_admin()
        self.st.secrets["access"]["approved_emails"] = ["someoneelse@example.com"]
        with self.assertRaises(Stopped):
            authentication.require_admin()

    def test_sign_out_stops_page(self):
        self.st.sidebar.button.return_value = True
        with self.assertRaises(Stopped):
            authentication.require_admin()
        self.st.logout.assert_called_once()

    def test_every_page_checks_access_before_executing_its_body(self):
        root = Path(__file__).resolve().parents[1]
        for path in [root / "Home.py", *sorted((root / "pages").glob("*.py"))]:
            with self.subTest(page=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                main = next(node for node in tree.body
                            if isinstance(node, ast.FunctionDef) and node.name == "main")
                self.assertEqual(ast.unparse(main.body[0]), "require_admin()")


if __name__ == "__main__":
    unittest.main()
