#!/bin/bash
set -x

gfortran defs.f90 linelist.f90 zeta.for voigt.f90 xsec.f90 constants.f90 modules.f90 problem.f90 && 
./a.out
