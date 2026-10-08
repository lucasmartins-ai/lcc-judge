import unittest

from research.tool_measurement_worker import validate_request, require_worker, expected_wc


class ToolMeasurementWorkerTests(unittest.TestCase):
    def test_worker_cannot_be_invoked_on_host(self):
        with self.assertRaises(RuntimeError):
            require_worker()

    def test_wc_counts_newlines_instead_of_unterminated_display_lines(self):
        counts=expected_wc('ação café\nlast partial row')
        self.assertEqual(counts['newlines'],1)
        self.assertEqual(counts['words'],5)
        self.assertEqual(counts['characters'],26)
        self.assertEqual(counts['bytes'],29)
        self.assertEqual(expected_wc('')['newlines'],0)

    def test_request_has_only_bounded_fixture_parameters(self):
        self.assertEqual(validate_request({'seed':42,'fixtures':3}),{'seed':42,'fixtures':3})
        for invalid in [{'seed':True,'fixtures':3},{'seed':42,'fixtures':0},
                        {'seed':42,'fixtures':257},{'seed':42,'fixtures':3,'source':'code'},
                        {'seed':42,'fixtures':3,'path':'/private'}, {'seed':-1,'fixtures':3}]:
            with self.assertRaises(ValueError):
                validate_request(invalid)

    def test_partial_tool_output_is_not_a_complete_measurement(self):
        from research.tool_measurement_worker import parse_integer_columns
        with self.assertRaises(ValueError):
            parse_integer_columns('10 20',3)
        with self.assertRaises(ValueError):
            parse_integer_columns('10 20 extra',3)
        self.assertEqual(parse_integer_columns('10\t20\t30\n',3),[10,20,30])


if __name__=='__main__':
    unittest.main()
