# PatentPath

## Project Overview

PatentPath is a project that helps users understand Indian patent basics, including patentability, provisional vs complete filing, fees and forms.

## User

A final-year ECE student at Prince College who built a low-cost IoT irrigation sensor and wants to file a provisional patent.

## The problem

The user is unsure whether the IoT irrigation sensor invention is patentable under Indian patent law. They need help understanding Section 3 exclusions, including Section 3(k), and how these exclusions may apply to their invention. They also need to understand how provisional patent filing works and which fee category applies to them. PatentPath aims to make these patent-related details easier to understand.

## Data Sources

- Patents Act, 1970
- Patents Rules, 2003 (as amended)
- Manual of Patent Office Practice and Procedure
- Guidelines for Computer-Related Inventions
- Patent Office fee schedule
- Sample granted patent specifications

## Hardest Problem

Applying Section 3 exclusions (for example, Section 3(k) software as such) correctly to an invention.

## Target Metric

Section 3 flags should agree with a reviewer on 80% or more of 20 invention scenarios.

## Current Progress

Building the FastAPI skeleton and quality gates. Live URL will be added from Day 5.
