"""
BSD 3-Clause License
Copyright (c) 2025-2025 Yingtian Chen
All rights reserved.
"""


import numpy as np


dtype_tree = {
	'names': (
		#  0 -  4
		'scale',           #  0
		'id',              #  1
		'desc_scale',      #  2
		'desc_id',         #  3
		'num_prog',        #  4
		#  5 -  9
		'pid',             #  5
		'upid',            #  6
		'desc_pid',        #  7
		'phantom',         #  8
		'sam_Mvir',        #  9
		# 10 - 14
		'Mvir',            # 10
		'Rvir',            # 11
		'rs',              # 12
		'vrms',            # 13
		'mmp?',            # 14
		# 15 - 19
		'scale_of_last_MM',# 15
		'vmax',            # 16
		'x',               # 17
		'y',               # 18
		'z',               # 19
		# 20 - 24
		'vx',              # 20
		'vy',              # 21
		'vz',              # 22
		'Jx',              # 23
		'Jy',              # 24
		# 25 - 29
		'Jz',              # 25
		'Spin',            # 26
		'Breadth_first_ID',# 27
		'Depth_first_ID',  # 28
		'Tree_root_ID',    # 29
		# 30 - 34
		'Orig_halo_ID',    # 30
		'Snap_idx',        # 31
		'Next_coprogenitor_depthfirst_ID',# 32
		'Last_progenitor_depthfirst_ID',  # 33
		'Last_mainleaf_depthfirst_ID',    # 34
		# 35 - 39
		'Tidal_Force',     # 35
		'Tidal_ID',        # 36
		'Rs_Klypin',       # 37
		'Mvir_all',        # 38
		'M200b',           # 39
		# 40 - 44
		'M200c',           # 40
		'M500c',           # 41
		'M2500c',          # 42
		'Xoff',            # 43
		'Voff',            # 44
		# 45 - 49
		'Spin_Bullock',    # 45
		'b_to_a',          # 46
		'c_to_a',          # 47
		'A[x]',            # 48
		'A[y]',            # 49
		# 50 - 54
		'A[z]',            # 50
		'b_to_a(500c)',    # 51
		'c_to_a(500c)',    # 52
		'A[x](500c)',      # 53
		'A[y](500c)',      # 54
		# 55 - 59
		'A[z](500c)',      # 55
		'T/|U|',           # 56
		'M_pe_Behroozi',   # 57
		'M_pe_Diemer',     # 58
		'Type',            # 59
		# 60 - 64
		'SM',              # 60
		'Gas',             # 61
		'BH_Mass',         # 62
	),
	'formats': (
		'f8', 'i8', 'f8', 'i8', 'i8', #  0 -  4
		'i8', 'i8', 'i8', 'i8', 'f8', #  5 -  9
		'f8', 'f8', 'f8', 'f8', 'i8', # 10 - 14
		'f8', 'f8', 'f8', 'f8', 'f8', # 15 - 19
		'f8', 'f8', 'f8', 'f8', 'f8', # 20 - 24
		'f8', 'f8', 'i8', 'i8', 'i8', # 25 - 29
		'i8', 'i8', 'i8', 'i8', 'i8', # 30 - 34
		'f8', 'i8', 'f8', 'f8', 'f8', # 35 - 39
		'f8', 'f8', 'f8', 'f8', 'f8', # 40 - 44
		'f8', 'f8', 'f8', 'f8', 'f8', # 45 - 49
		'f8', 'f8', 'f8', 'f8', 'f8', # 50 - 54
		'f8', 'f8', 'f8', 'f8', 'i8', # 55 - 59
		'f8', 'f8', 'f8',             # 60 - 64
	)
}

fmt_tree = (
	'%.5f %i %.5f %i %i '       # 0 - 4       
	'%i %i %i %i %.5e '         # 5 - 9
	'%.5e %.5f %.5f %.5f  %i '  # 10 - 14
	'%.5f %.6f %.5f %.5f %.5f ' # 15 - 19
	'%.3f %.3f %.3f %.3e %.3e ' # 20 - 24
	'%.3e %.5f %i %i %i '       # 25 - 29
	'%i %i %i %i %i '           # 30 - 34
	'%.5f %i %.4f %i %i '       # 35 - 39
	'%i %i %i %.5f %.2f '       # 40 - 44
	'%.5f %.5f %.5f %.5f %.5f ' # 45 - 49
	'%.5f %.5f %.5f %.5f %.5f ' # 50 - 54
	'%.5f %.4f %i %i %i '       # 55 - 59
	'%i %i %i'                  # 60 - 64
)