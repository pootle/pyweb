#!/usr/bin/python3
"""
Extends camSequence with a masking capability
"""
import camSequence

class Masked_sequence(camSequence.Image_sequence):
    def fetchmasksize(self):
        pass