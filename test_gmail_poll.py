"""Unit tests for gmail_poll helpers.

Run with the gmail-mcp venv python (which has googleapiclient on the path):
    /Users/wolfgang/code/gmail-mcp/venv/bin/python -m unittest test_gmail_poll -v
"""

import unittest

import gmail_poll


class AllowedSendersFromConfig(unittest.TestCase):
    def test_present(self):
        cfg = {'allowed_senders': ['a@x.com', 'b@y.com']}
        self.assertEqual(
            gmail_poll._allowed_senders(cfg),
            ['a@x.com', 'b@y.com'],
        )

    def test_missing_falls_back_to_default(self):
        cfg = {'default_account': 'foo@example.com'}
        self.assertEqual(
            gmail_poll._allowed_senders(cfg),
            ['wolfgangmeyers@gmail.com'],
        )

    def test_empty_list_is_respected(self):
        # Default only when key is entirely missing — an explicit empty list stays empty.
        cfg = {'allowed_senders': []}
        self.assertEqual(gmail_poll._allowed_senders(cfg), [])


class SenderAddressFromHeader(unittest.TestCase):
    def test_bare_address(self):
        self.assertEqual(
            gmail_poll.sender_address_from_header('wolfgangmeyers@gmail.com'),
            'wolfgangmeyers@gmail.com',
        )

    def test_display_name_form(self):
        self.assertEqual(
            gmail_poll.sender_address_from_header('Wolfgang Meyers <wolfgangmeyers@gmail.com>'),
            'wolfgangmeyers@gmail.com',
        )

    def test_quoted_display_name(self):
        self.assertEqual(
            gmail_poll.sender_address_from_header('"Meyers, Wolfgang" <wolfgangmeyers@gmail.com>'),
            'wolfgangmeyers@gmail.com',
        )

    def test_empty(self):
        self.assertEqual(gmail_poll.sender_address_from_header(''), '')
        self.assertEqual(gmail_poll.sender_address_from_header(None), '')


class SenderToAgentName(unittest.TestCase):
    def test_simple_local_part(self):
        self.assertEqual(
            gmail_poll.sender_to_agent_name('wolfgangmeyers@gmail.com'),
            'wolfgangmeyers',
        )

    def test_dotted_local_part_sanitized(self):
        self.assertEqual(
            gmail_poll.sender_to_agent_name('first.last@example.com'),
            'first_last',
        )

    def test_plus_addressing_sanitized(self):
        self.assertEqual(
            gmail_poll.sender_to_agent_name('user+tag@example.com'),
            'user_tag',
        )

    def test_empty_falls_back_to_user(self):
        self.assertEqual(gmail_poll.sender_to_agent_name(''), 'user')
        self.assertEqual(gmail_poll.sender_to_agent_name(None), 'user')

    def test_leading_non_alnum_falls_back_to_user(self):
        # mailbox_send.py's regex requires the first char to be alphanumeric.
        self.assertEqual(gmail_poll.sender_to_agent_name('-weird@example.com'), 'user')
        self.assertEqual(gmail_poll.sender_to_agent_name('_internal@example.com'), 'user')


if __name__ == '__main__':
    unittest.main()
