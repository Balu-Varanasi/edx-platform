"""
Test signal handlers for completion.
"""

from datetime import datetime

from completion import handlers
from completion.models import BlockCompletion
from completion.test_utils import CompletionSetUpMixin
import ddt
from django.test import TestCase
from mock import patch
from pytz import utc
import six
from xblock.completable import XBlockCompletionMode
from xblock.core import XBlock

from lms.djangoapps.grades.signals.signals import PROBLEM_WEIGHTED_SCORE_CHANGED
from openedx.core.djangolib.testing.utils import skip_unless_lms


class CustomScorableBlock(XBlock):
    """
    A scorable block with a custom completion strategy.
    """
    has_score = True
    has_custom_completion = True
    completion_mode = XBlockCompletionMode.COMPLETABLE


class ExcludedScorableBlock(XBlock):
    """
    A scorable block that is excluded from completion tracking.
    """
    has_score = True
    has_custom_completion = False
    completion_mode = XBlockCompletionMode.EXCLUDED


@ddt.ddt
@skip_unless_lms
class ScorableCompletionHandlerTestCase(CompletionSetUpMixin, TestCase):
    """
    Test the signal handler
    """
    COMPLETION_SWITCH_ENABLED = True

    def setUp(self):
        super(ScorableCompletionHandlerTestCase, self).setUp()
        self.block_key = self.course_key.make_usage_key(block_type='problem', block_id='red')

    def call_scorable_block_completion_handler(self, block_key, score_deleted=None):
        """
        Call the scorable completion signal handler for the specified block.

        Optionally takes a value to pass as score_deleted.
        """
        if score_deleted is None:
            params = {}
        else:
            params = {'score_deleted': score_deleted}
        handlers.scorable_block_completion(
            sender=self,
            user_id=self.user.id,
            course_id=six.text_type(self.course_key),
            usage_id=six.text_type(block_key),
            weighted_earned=0.0,
            weighted_possible=3.0,
            modified=datetime.utcnow().replace(tzinfo=utc),
            score_db_table='submissions',
            **params
        )

    @ddt.data(
        (True, 0.0),
        (False, 1.0),
        (None, 1.0),
    )
    @ddt.unpack
    def test_handler_submits_completion(self, score_deleted, expected_completion):
        self.call_scorable_block_completion_handler(self.block_key, score_deleted)
        completion = BlockCompletion.objects.get(
            user=self.user,
            course_key=self.course_key,
            block_key=self.block_key,
        )
        self.assertEqual(completion.completion, expected_completion)

    @XBlock.register_temp_plugin(CustomScorableBlock, 'custom_scorable')
    def test_handler_skips_custom_block(self):
        custom_block_key = self.course_key.make_usage_key(block_type='custom_scorable', block_id='green')
        self.call_scorable_block_completion_handler(custom_block_key)
        completion = BlockCompletion.objects.filter(
            user=self.user,
            course_key=self.course_key,
            block_key=custom_block_key,
        )
        self.assertFalse(completion.exists())

    @XBlock.register_temp_plugin(ExcludedScorableBlock, 'excluded_scorable')
    def test_handler_skips_excluded_block(self):
        excluded_block_key = self.course_key.make_usage_key(block_type='excluded_scorable', block_id='blue')
        self.call_scorable_block_completion_handler(excluded_block_key)
        completion = BlockCompletion.objects.filter(
            user=self.user,
            course_key=self.course_key,
            block_key=excluded_block_key,
        )
        self.assertFalse(completion.exists())

    def test_signal_calls_handler(self):
        with patch('completion.handlers.scorable_block_completion') as mock_handler:
            PROBLEM_WEIGHTED_SCORE_CHANGED.send_robust(
                sender=self,
                user_id=self.user.id,
                course_id=six.text_type(self.course_key),
                usage_id=six.text_type(self.block_key),
                weighted_earned=0.0,
                weighted_possible=3.0,
                modified=datetime.utcnow().replace(tzinfo=utc),
                score_db_table='submissions',
            )
        mock_handler.assert_called()


@skip_unless_lms
class DisabledCompletionHandlerTestCase(CompletionSetUpMixin, TestCase):
    """
    Test that disabling the ENABLE_COMPLETION_TRACKING waffle switch prevents
    the signal handler from submitting a completion.
    """
    COMPLETION_SWITCH_ENABLED = False

    def setUp(self):
        super(DisabledCompletionHandlerTestCase, self).setUp()
        self.block_key = self.course_key.make_usage_key(block_type='problem', block_id='red')

    def test_disabled_handler_does_not_submit_completion(self):
        handlers.scorable_block_completion(
            sender=self,
            user_id=self.user.id,
            course_id=six.text_type(self.course_key),
            usage_id=six.text_type(self.block_key),
            weighted_earned=0.0,
            weighted_possible=3.0,
            modified=datetime.utcnow().replace(tzinfo=utc),
            score_db_table='submissions',
        )
        with self.assertRaises(BlockCompletion.DoesNotExist):
            BlockCompletion.objects.get(
                user=self.user,
                course_key=self.course_key,
                block_key=self.block_key
            )
