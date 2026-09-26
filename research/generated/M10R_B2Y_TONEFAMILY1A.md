# M10-R B2Y TONEFAMILY1A

Focused cross-color-family audit for _B2YMODE:STILL_CONTRAST:MEDIUM.

## M10R-30.22.23.34

- Descriptor size 176; SHA 5cfbfbf24b99ee035b345f644736e8bdce9b00678c8b96d1c455476474e855a5
- Descriptor decoded core: {'size': 176, 'enable_u8': 1, 'field_04_u32': 0, 'resolution_code_08_u8': 1, 'mode_0c_u32': 1, 'field_14_u16': 0, 'field_18_u8': 0, 'limits_78_94_u16': [16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383], 'tail_a0_end_hex': '00000000000000000000000000000000'}
- TBL0 active SHA 2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00; min/max 19431/35130
- TBL1 active SHA 2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00
- TBL0 == TBL1 active: True

## M10-3.22.23.38

- Descriptor size 164; SHA 9fb203aa86e0c62a3a6699f10c91dedc557153644f167d830526230559dec24c
- Descriptor decoded core: {'size': 164, 'enable_u8': 1, 'field_04_u32': 0, 'resolution_code_08_u8': 1, 'mode_0c_u32': 1, 'field_14_u16': 0, 'field_18_u8': 0, 'limits_78_94_u16': [16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383], 'tail_a0_end_hex': '00000000'}
- TBL0 active SHA 2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00; min/max 19431/35130
- TBL1 active SHA fc11928e47c9e5fc1705834f89fd3e5f5b077eaa50052115f0cdb93e22aea743
- TBL0 == TBL1 active: False

## M10P-4.22.23.34

- Descriptor size 164; SHA 9fb203aa86e0c62a3a6699f10c91dedc557153644f167d830526230559dec24c
- Descriptor decoded core: {'size': 164, 'enable_u8': 1, 'field_04_u32': 0, 'resolution_code_08_u8': 1, 'mode_0c_u32': 1, 'field_14_u16': 0, 'field_18_u8': 0, 'limits_78_94_u16': [16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383, 0, 16383], 'tail_a0_end_hex': '00000000'}
- TBL0 active SHA 2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00; min/max 19431/35130
- TBL1 active SHA fc11928e47c9e5fc1705834f89fd3e5f5b077eaa50052115f0cdb93e22aea743
- TBL0 == TBL1 active: False

## Comparisons

- M10R_vs_M10: {'descriptor_common_prefix_diff_byte_count': 0, 'descriptor_diff_runs': [], 'descriptor_size_a': 176, 'descriptor_size_b': 164, 'descriptor_extra_a_hex': '000000000000000000000000', 'descriptor_extra_b_hex': '', 'tbl0_active_equal': True, 'tbl0_differing_entries': 0, 'tbl0_first_diff_indices': [], 'tbl0_max_abs_q15_gain_delta': 0, 'functional_curve_max_abs_code_delta': 0, 'functional_curve_mean_abs_code_delta': 0.0, 'functional_curve_differing_codes': 0}
- M10R_vs_M10P: {'descriptor_common_prefix_diff_byte_count': 0, 'descriptor_diff_runs': [], 'descriptor_size_a': 176, 'descriptor_size_b': 164, 'descriptor_extra_a_hex': '000000000000000000000000', 'descriptor_extra_b_hex': '', 'tbl0_active_equal': True, 'tbl0_differing_entries': 0, 'tbl0_first_diff_indices': [], 'tbl0_max_abs_q15_gain_delta': 0, 'functional_curve_max_abs_code_delta': 0, 'functional_curve_mean_abs_code_delta': 0.0, 'functional_curve_differing_codes': 0}
- M10_vs_M10P: {'descriptor_common_prefix_diff_byte_count': 0, 'descriptor_diff_runs': [], 'descriptor_size_a': 164, 'descriptor_size_b': 164, 'descriptor_extra_a_hex': '', 'descriptor_extra_b_hex': '', 'tbl0_active_equal': True, 'tbl0_differing_entries': 0, 'tbl0_first_diff_indices': [], 'tbl0_max_abs_q15_gain_delta': 0, 'functional_curve_max_abs_code_delta': 0, 'functional_curve_mean_abs_code_delta': 0.0, 'functional_curve_differing_codes': 0}

## Boundary

If M10-R differs only in the calibrated Q15 table while the descriptor's already-used core fields match, the current renderer already carries the principal model-specific tone calibration.
Any descriptor-only differences must be mapped to proven hardware semantics before being promoted.
