from pylint.reporters.json import JSONReporter


def json_reporter_handle_message(self, msg):
    """Manage message of different type and in the context of path."""
    self.messages.append({
        'path': msg.path,
        'abspath': msg.abspath,
        'line': msg.line,
        'column': msg.column,
        'module': msg.module,
        'obj': msg.obj,
        'msg': msg.msg,
        'msg_id': msg.msg_id,
        'symbol': msg.symbol,
        'C': msg.C,
        'category': msg.category,
    })

JSONReporter.handle_message = json_reporter_handle_message


def output_lint_result(lint_result, msg_template):
    lint_module = lint_result[0]['module']
    if lint_module:
        print("************* Module {module}".format(module=lint_module))
    else:
        print("************* ")
    for msg in lint_result:
        print(msg_template.format(**msg))
