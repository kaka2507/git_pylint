import os
import re

import git

from git_pylint import sysutils

EMPTY_TREE = git.Git().hash_object('/dev/null', t='tree')

HEADER_REGEX = re.compile(r'@@ -(?P<a_start_line_number>\d+)(?:,(?P<a_chunk_size>\d+))? \+(?P<b_start_line_number>\d+)(?:,(?P<b_chunk_size>\d+))? @@.*')
DIFF_LINE_REGEX = re.compile(r'([-+])(.*)')
NO_NEWLINE_AT_END_OF_FILE = r'\ No newline at end of file'


def parse_unidiff(unidiff):
    unidiff = unidiff.decode('utf-8')
    diff = []
    for line in filter(None, unidiff.split('\n')):
        header_match = HEADER_REGEX.match(line)
        if header_match:
            a_start_line_number = int(header_match.group('a_start_line_number'))
            a_chunk_size = header_match.group('a_chunk_size')
            a_chunk_size = int(a_chunk_size) if a_chunk_size else 1
            if a_chunk_size == 0:
                a_start_line_number += 1
            b_start_line_number = int(header_match.group('b_start_line_number'))
            b_chunk_size = header_match.group('b_chunk_size')
            b_chunk_size = int(b_chunk_size) if b_chunk_size else 1
            if b_chunk_size == 0:
                b_start_line_number += 1
            d = {
                'a_start_line_number': a_start_line_number,
                'b_start_line_number': b_start_line_number,
                'lines': []
            }
            diff.append(d)
            continue
        diff_line_match = DIFF_LINE_REGEX.match(line)
        if diff_line_match:
            d['lines'].append(diff_line_match.groups())
            continue
        if line == NO_NEWLINE_AT_END_OF_FILE:
            continue
        raise Exception('Wrong diff format: ' + line)
    return diff


def get_line_map(gitdiff):
    diff = parse_unidiff(gitdiff.diff)
    line_map = [None]
    a_line_number = 1
    b_line_number = 1

    for sec in diff:
        while b_line_number < sec['b_start_line_number']:
            line_map.append(a_line_number)
            a_line_number += 1
            b_line_number += 1

        for line in sec['lines']:
            if line[0] == '-':
                a_line_number += 1
            else:
                line_map.append(None)
                b_line_number += 1
    b_line_count = sysutils.get_line_count(gitdiff.b_path)
    while b_line_number <= b_line_count:
        line_map.append(a_line_number)
        a_line_number += 1
        b_line_number += 1
    return line_map


def get_merge_base(repo, target_branch, source_branch):
    merge_bases = repo.merge_base(target_branch, source_branch)
    try:
        return merge_bases[0].hexsha
    except IndexError:
        return EMPTY_TREE


def get_diffs(repo, a_tree, b_tree, ignore_names, ignore_patterns):
    diff_index = repo.tree(a_tree).diff(b_tree, create_patch=True, unified=0)
    return [
        diff
        for diff in diff_index
        if diff.b_blob
           and sysutils.is_python_file(diff.b_path)
           and diff.a_blob != diff.b_blob
           and not sysutils.is_ignored(os.path.basename(diff.b_path), ignore_names, ignore_patterns)
    ]
