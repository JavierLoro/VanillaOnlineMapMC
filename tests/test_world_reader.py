from unittest.mock import patch
import unittest

from backend import world_reader as reader


def packed(values, bits):
    """Encode padded longs independently of the production decoder."""
    per_long = 64 // bits
    result = []
    for start in range(0, len(values), per_long):
        word = sum(value << (i * bits) for i, value in enumerate(values[start:start+per_long]))
        result.append(word if word < 2**63 else word - 2**64)
    return result


class WorldReaderTests(unittest.TestCase):
    def test_all_palette_encodings_preserve_properties(self):
        expected = ("minecraft:oak_stairs", (("facing", "east"), ("half", "top")))
        for entry in (
            {"Name": "minecraft:oak_stairs", "Properties": {"half": "top", "facing": "east"}},
            {"id": "minecraft:oak_stairs", "properties": {"facing": "east", "half": "top"}},
            {"": {"id": "oak_stairs", "properties": {"half": "top", "facing": "east"}}},
        ):
            with self.subTest(entry=entry):
                self.assertEqual(reader.normalize_block_state(entry), expected)
        for entry in ("stone", "minecraft:stone", {"": "minecraft:stone"},
                      {"Name": "minecraft:stone"}, {"id": "minecraft:stone"}):
            self.assertEqual(reader.normalize_block_state(entry), ("minecraft:stone", ()))
        for invalid in (None, {}, {"id": 3}, {"id": "stone", "properties": []},
                        {"id": "stone", "properties": {"axis": 1}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reader.normalize_block_state(invalid)

    def test_surface_height_is_signed_world_y_and_zero_is_empty(self):
        self.assertIsNone(reader.surface_y(0))
        self.assertEqual(reader.surface_y(1), -64)
        self.assertEqual(reader.surface_y(65), 0)
        self.assertEqual(reader.surface_y(384), 319)
        self.assertEqual(reader.surface_y(64, min_y=0), 63)

    def test_section_unpack_once_coordinates_and_more_than_four_bits(self):
        palette = [f"minecraft:test_{i}" for i in range(17)]
        values = [(i * 7) % 17 for i in range(4096)]
        sections = [{"Y": -1, "block_states": {"palette": palette, "data": packed(values, 5)}}]
        block_reader = reader.BlockStateReader(sections)
        with patch.object(reader, "_unpack_block_indices", wraps=reader._unpack_block_indices) as unpack:
            for z in range(16):
                for x in range(16):
                    self.assertEqual(block_reader.state_at(x, -2, z)[0],
                                     palette[values[14 * 256 + z * 16 + x]])
            self.assertEqual(unpack.call_count, 1)

    def test_legacy_four_by_four_interface_with_compact_states(self):
        section = {"Y": 4, "block_states": {"palette": [{"": "minecraft:dirt_path"}]}}
        blocks = reader._top_block_4x4([section], [129] * 256)
        self.assertEqual(blocks, {(x, z): "minecraft:dirt_path" for z in range(4) for x in range(4)})
        self.assertEqual(reader._top_block_4x4([section], [0] * 256)[0, 0], "minecraft:air")

    def test_invalid_packed_states_do_not_silently_become_air(self):
        for states in ({"palette": ["stone", "dirt"]},
                       {"palette": ["stone", "dirt"], "data": [0]},
                       {"palette": ["stone", "dirt"], "data": packed([15] * 4096, 4)}):
            with self.subTest(states=str(states)[:60]), self.assertRaises(ValueError):
                reader.BlockStateReader([{"Y": 0, "block_states": states}]).state_at(0, 0, 0)


if __name__ == "__main__":
    unittest.main()
