#!/usr/bin/env python3

import configparser
import json
import os
import re
import sys
from io import StringIO

import astroid
import git
from gitdb.exc import BadName, BadObject
from pylint import lint
from pylint.reporters.json import JSONReporter
from pylint.utils import MSG_TYPES_STATUS

import diffutils
import sysutils
import reporter


DEFAULT_TARGET_BRANCH = 'master'
DIFF_MODE_FILE = 'file'
DIFF_MODE_LINE = 'line'
DIFF_MODES = [DIFF_MODE_FILE, DIFF_MODE_LINE]
DEFAULT_DIFF_MODE = DIFF_MODE_LINE
CHECKOUT_MODE_FILE = 'file'
CHECKOUT_MODE_TREE = 'tree'
CHECKOUT_MODES = [CHECKOUT_MODE_FILE, CHECKOUT_MODE_TREE]
DEFAULT_OUTPUT_FORMAT = 'text'
DEFAULT_MSG_TEMPLATE = '{path} ({line}:{column}) | {msg_id}: {symbol} | {obj}: {msg}'

NUMBER_REGEX = re.compile(r'\b\d+\b')

has_run = False


def change_path(lint_result, path, working_dir):
    for msg in lint_result:
        msg['path'] = path
        msg['abspath'] = os.path.join(working_dir, path)
        root, _ = os.path.splitext(path)
        msg['module'] = root.replace('/', '.')


def my_lint(original_path, args, repo=None, tree=None, blob=None):
    global has_run
    path = original_path
    top_temp_path = None

    try:
        if repo:
            if tree:
                sysutils.checkout(repo, tree)
                if has_run:
                    astroid.builder.MANAGER.astroid_cache.clear()
            if blob:
                if blob != repo.git.hash_object(path):
                    path, top_temp_path = sysutils.mktemp(path)
                    sysutils.unpack_file(repo, blob, path)

        io = StringIO()
        run = lint.Run(args + [path], reporter=JSONReporter(io), do_exit=False)
        fatal_error = run.linter.msg_status & 1
        output = io.getvalue()
        lint_result = json.loads(output) if output else []
        if path != original_path:
            change_path(lint_result, original_path, working_dir=repo.working_tree_dir)

    finally:
        has_run = True
        if repo:
            if top_temp_path:
                sysutils.rmtree(top_temp_path)
            if tree:
                repo.head.reset(index=True, working_tree=True)

    return fatal_error, lint_result


def filter_lint_result(b_lint_result, a_lint_result, line_map):
    def hash_msg(msg, transform_line):
        line = msg['line']
        line = line_map[line] if transform_line else line
        msg_txt = msg['msg']
        first_line, sep, remaining_lines = msg_txt.partition('\n')
        if first_line and first_line[-1] == ')' and '(' in first_line:
            idx = first_line.rindex('(')
            bracketed_str = NUMBER_REGEX.sub('', first_line[idx:])
            msg_txt = first_line[:idx] + bracketed_str + sep + remaining_lines
        return line, msg['column'], msg['msg_id'], msg_txt

    a_msg_set = {hash_msg(msg, False) for msg in a_lint_result}
    lint_result = [msg for msg in b_lint_result if hash_msg(msg, True) not in a_msg_set]
    return lint_result


def diff_lint(diff, args, repo=None, should_lint_a=True, a_tree=None, b_tree=None):
    if b_tree:
        fatal_error, lint_result = my_lint(diff.b_path, args, repo=repo, tree=b_tree)
    else:
        fatal_error, lint_result = my_lint(diff.b_path, args, repo=repo, blob=diff.b_blob.hexsha)
    if should_lint_a and lint_result and diff.a_blob:
        if a_tree:
            a_fatal_error, a_lint_result = my_lint(diff.a_path, args, repo=repo, tree=a_tree)
        else:
            a_fatal_error, a_lint_result = my_lint(diff.b_path, args, repo=repo, blob=diff.a_blob.hexsha)
        if a_fatal_error:
            fatal_error = 1
            lint_result = []
        elif a_lint_result:
            line_map = diffutils.get_line_map(diff)
            lint_result = filter_lint_result(lint_result, a_lint_result, line_map)
    return fatal_error, lint_result


def main():
    args = sys.argv[1:]
    ci_server = os.getenv('CI_SERVER') == 'yes'
    repo_dir = os.getcwd()
    repo = git.Repo(repo_dir)
    rcfile = os.path.join(os.getenv('HOME'), 'pylint.conf')
    rcfile = sysutils.extract_option(args, ['--rcfile'], rcfile)
    args = ['--rcfile', rcfile] + args
    config = configparser.ConfigParser()
    config.read(rcfile)

    source_branch = os.getenv('CI_COMMIT_SHA')
    if not source_branch:
        source_branch = repo.head.commit.hexsha
        b_tree = repo.git.write_tree()
    else:
        b_tree = source_branch
    target_branch = sysutils.extract_option(args, ['--target-branch'], DEFAULT_TARGET_BRANCH)
    if ci_server:
        try:
            repo.commit('origin/' + target_branch)
            target_branch = 'origin/' + target_branch
        except (BadName, BadObject):
            pass

    def append(l, x):
        l.append(x)
        return l
    python_path = sysutils.extract_option(args, ['--python-path'], [], append)
    sys.path += python_path

    try:
        ignore_names = config.get('MASTER', 'ignore').split(',')
    except (configparser.NoSectionError, configparser.NoOptionError):
        ignore_names = []
    ignore_names = sysutils.extract_option(args, ['--ignore'], ignore_names, lambda _, csv: csv.split(','))

    try:
        ignore_patterns = map(re.compile, config.get('MASTER', 'ignore-patterns').split(','))
    except (configparser.NoSectionError, configparser.NoOptionError):
        ignore_patterns = []
    ignore_patterns = sysutils.extract_option(args, ['--ignore-patterns'], ignore_patterns, lambda _, regexp_csv: map(re.compile, regexp_csv.split(',')))
    ignore_patterns = list(ignore_patterns)

    sysutils.extract_option(args, ['-f', '--output-format'], DEFAULT_OUTPUT_FORMAT)
    try:
        msg_template = config.get('REPORTS', 'msg-template')
    except (configparser.NoSectionError, configparser.NoOptionError):
        msg_template = DEFAULT_MSG_TEMPLATE
    msg_template = sysutils.extract_option(args, ['--msg-template'], msg_template)

    diff_mode = sysutils.extract_option(args, ['--diff-mode'], DEFAULT_DIFF_MODE)
    if diff_mode not in DIFF_MODES:
        sys.exit('Unrecognised diff mode')
    checkout_mode = sysutils.extract_option(args, ['--checkout-mode'], CHECKOUT_MODE_FILE)
    if checkout_mode not in CHECKOUT_MODES:
        sys.exit('Unrecognised checkout mode')

    a_tree = diffutils.get_merge_base(repo, target_branch, source_branch)
    diffs = diffutils.get_diffs(repo, a_tree, b_tree, ignore_names, ignore_patterns)
    if not diffs:
        return

    main_exit_code = 0
    msg_count = 0
    should_lint_a = diff_mode == DIFF_MODE_LINE
    if checkout_mode != CHECKOUT_MODE_TREE:
        a_tree = None
        b_tree = None

    for diff in diffs:
        fatal_error, lint_result = diff_lint(diff, args, repo, should_lint_a, a_tree, b_tree)
        if lint_result:
            reporter.output_lint_result(lint_result, msg_template)
            for msg in lint_result:
                main_exit_code |= MSG_TYPES_STATUS[msg['C']]
            msg_count += len(lint_result)
        if fatal_error:
            main_exit_code |= 1
            break

    if (main_exit_code & 1) == 0:
        print("\n%s problem%s reported\n" % (msg_count, 's' if msg_count > 1 else ''))
    sys.exit(main_exit_code)


if __name__ == '__main__':
    main()
