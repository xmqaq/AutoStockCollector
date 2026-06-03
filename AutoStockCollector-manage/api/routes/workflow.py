"""
选股工作流API路由
"""
from flask import Blueprint, request, jsonify, Response, stream_with_context
from datetime import datetime
import uuid
import threading
from modules.workflow import (
    Workflow, WorkflowStorage, WorkflowExecutor, WorkflowNode, WorkflowEdge,
    WorkflowExecution, WorkflowExecutionStorage, ExecutionStatus,
    WorkflowTemplate, WorkflowTemplateStorage
)
from modules.workflow.sse import WorkflowSSE
from utils.logger import get_logger


logger = get_logger(__name__)

workflow_bp = Blueprint('workflow', __name__, url_prefix='/api/v1/workflow')
workflow_storage = WorkflowStorage()
execution_storage = WorkflowExecutionStorage()
template_storage = WorkflowTemplateStorage()


@workflow_bp.route('', methods=['GET'])
def list_workflows():
    """获取所有工作流"""
    try:
        enabled = request.args.get('enabled')
        enabled_filter = None if enabled is None else enabled.lower() == 'true'

        workflows = workflow_storage.list_workflows(enabled=enabled_filter)
        return jsonify({
            'success': True,
            'data': [w.to_dict() for w in workflows]
        })
    except Exception as e:
        logger.error(f"List workflows failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>', methods=['GET'])
def get_workflow(workflow_id):
    """获取单个工作流"""
    try:
        workflow = workflow_storage.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        return jsonify({
            'success': True,
            'data': workflow.to_dict()
        })
    except Exception as e:
        logger.error(f"Get workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('', methods=['POST'])
def create_workflow():
    """创建新工作流"""
    try:
        data = request.get_json()
        workflow_id = data.get('id') or str(uuid.uuid4())

        workflow = Workflow(
            id=workflow_id,
            name=data.get('name', 'New Workflow'),
            description=data.get('description', ''),
            nodes=[WorkflowNode.from_dict(n) if isinstance(n, dict) else n for n in data.get('nodes', [])],
            edges=[WorkflowEdge.from_dict(e) if isinstance(e, dict) else e for e in data.get('edges', [])],
            enabled=data.get('enabled', True),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            tags=data.get('tags', [])
        )

        if workflow_storage.save_workflow(workflow):
            return jsonify({
                'success': True,
                'data': workflow.to_dict()
            }), 201
        else:
            return jsonify({'success': False, 'error': 'Failed to save workflow'}), 500

    except Exception as e:
        logger.error(f"Create workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>', methods=['PUT'])
def update_workflow(workflow_id):
    """更新工作流"""
    try:
        data = request.get_json()
        workflow = workflow_storage.get_workflow(workflow_id)

        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        if 'name' in data:
            workflow.name = data['name']
        if 'description' in data:
            workflow.description = data['description']
        if 'nodes' in data:
            workflow.nodes = data['nodes']
        if 'edges' in data:
            workflow.edges = data['edges']
        if 'enabled' in data:
            workflow.enabled = data['enabled']
        if 'tags' in data:
            workflow.tags = data['tags']

        workflow.updated_at = datetime.now().isoformat()

        if workflow_storage.save_workflow(workflow):
            return jsonify({
                'success': True,
                'data': workflow.to_dict()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save workflow'}), 500

    except Exception as e:
        logger.error(f"Update workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>', methods=['DELETE'])
def delete_workflow(workflow_id):
    """删除工作流"""
    try:
        if workflow_storage.delete_workflow(workflow_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404
    except Exception as e:
        logger.error(f"Delete workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/run', methods=['POST'])
def run_workflow(workflow_id):
    """异步执行工作流"""
    try:
        workflow = workflow_storage.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        if not workflow.enabled:
            return jsonify({'success': False, 'error': 'Workflow is disabled'}), 400

        # Pre-flight checks
        nodes_list = [n.to_dict() if hasattr(n, 'to_dict') else n for n in workflow.nodes]
        is_quant = getattr(workflow, 'workflow_type', '') == 'quant_multi_factor'
        if not nodes_list and not is_quant:
            return jsonify({'success': False, 'error': '工作流步骤为空，请先编辑工作流添加节点'}), 400

        has_ai_node = any(n.get('type') == 'ai_agent' for n in nodes_list)
        if has_ai_node:
            try:
                from config.database import DatabaseConfig as _DB
                _db = _DB.get_database()
                ai_key_count = _db["ai_keys"].count_documents({"enabled": True, "api_key": {"$exists": True, "$ne": ""}})
                if ai_key_count == 0:
                    return jsonify({'success': False, 'error': '工作流包含AI节点，但未配置有效的AI API Key，请先在"AI Key管理"页面添加并启用Key'}), 400
            except Exception:
                pass  # non-fatal, allow execution to proceed

        existing = execution_storage.get_running_execution(workflow_id)
        if existing:
            # Check for stale execution: if running for more than 10 minutes, auto-terminate it
            stale = False
            try:
                started_dt = datetime.fromisoformat(existing.started_at)
                if (datetime.now() - started_dt).total_seconds() > 600:
                    stale = True
            except Exception:
                stale = True  # unparseable timestamp → treat as stale

            if stale:
                execution_storage.fail_execution(existing.id, "执行超时（>10分钟），已自动终止")
                logger.warning(f"Stale execution {existing.id} auto-terminated for workflow {workflow_id}")
            else:
                return jsonify({
                    'success': False,
                    'error': '工作流正在执行中，请等待完成',
                    'execution_id': existing.id,
                    'status': existing.status
                }), 409

        execution_id = str(uuid.uuid4())
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            status=ExecutionStatus.RUNNING.value,
            progress=0,
            current_node='',
            current_step='准备执行...',
            steps=[],
            started_at=datetime.now().isoformat()
        )
        execution_storage.create_execution(execution)

        params = request.get_json() or {}
        nodes = nodes_list  # already computed in pre-flight check
        edges = [e.to_dict() if hasattr(e, 'to_dict') else e for e in workflow.edges]

        WorkflowSSE.cleanup(execution_id)

        def make_progress_callback(exec_id: str):
            def progress_callback(
                node_id: str,
                node_label: str,
                step: str,
                progress: float,
                detail: dict = None
            ):
                step_data = {
                    'node_id': node_id,
                    'node_label': node_label,
                    'step': step,
                    'progress': progress,
                    'detail': detail or {},
                    'timestamp': datetime.now().isoformat()
                }
                execution_storage.update_progress(
                    exec_id, progress, node_id, step, step_data
                )
                WorkflowSSE.publish(exec_id, 'progress', step_data)
            return progress_callback

        def make_background_runner(exec_id, start_idx=0, codes_override=None):
            def execute_in_background():
                try:
                    executor = WorkflowExecutor(workflow_id, exec_id, make_progress_callback(exec_id))
                    result = executor.execute(nodes, edges, params,
                                              start_from_idx=start_idx,
                                              codes_override=codes_override)
                    if result.get('success'):
                        execution_storage.complete_execution(exec_id, result)
                        workflow_storage.update_last_run(workflow_id)
                        WorkflowSSE.publish(exec_id, 'complete', {'status': 'completed', 'result': result})
                    elif result.get('paused'):
                        execution_storage.pause_execution(
                            exec_id,
                            result.get('paused_node_idx', 0),
                            result.get('codes', [])
                        )
                        WorkflowSSE.publish(exec_id, 'paused', {'status': 'paused'})
                    elif result.get('cancelled'):
                        execution_storage.cancel_execution(exec_id)
                        WorkflowSSE.publish(exec_id, 'cancelled', {'status': 'cancelled'})
                    else:
                        err = result.get('error', 'Unknown error')
                        execution_storage.fail_execution(exec_id, err)
                        WorkflowSSE.publish(exec_id, 'error', {'status': 'failed', 'error': err})
                except Exception as e:
                    import traceback
                    logger.error(f"Background execution failed: {e}\n{traceback.format_exc()}")
                    execution_storage.fail_execution(exec_id, str(e))
                    WorkflowSSE.publish(exec_id, 'error', {'status': 'failed', 'error': str(e)})
                finally:
                    WorkflowSSE.cleanup(exec_id)
            return execute_in_background

        # Dispatch to quantitative multi-factor executor if workflow_type matches
        if getattr(workflow, 'workflow_type', '') == 'quant_multi_factor':
            def make_quant_runner(exec_id):
                def run():
                    try:
                        from modules.workflow.quant_executor import QuantMultiFactorExecutor
                        executor = QuantMultiFactorExecutor(workflow_id, exec_id, make_progress_callback(exec_id))
                        result = executor.execute()
                        if result.get('success'):
                            execution_storage.complete_execution(exec_id, result)
                            workflow_storage.update_last_run(workflow_id)
                            WorkflowSSE.publish(exec_id, 'complete', {'status': 'completed', 'result': result})
                        else:
                            err = result.get('error', 'Unknown error')
                            execution_storage.fail_execution(exec_id, err)
                            WorkflowSSE.publish(exec_id, 'error', {'status': 'failed', 'error': err})
                    except Exception as e:
                        import traceback
                        logger.error(f"Quant execution failed: {e}\n{traceback.format_exc()}")
                        execution_storage.fail_execution(exec_id, str(e))
                        WorkflowSSE.publish(exec_id, 'error', {'status': 'failed', 'error': str(e)})
                    finally:
                        WorkflowSSE.cleanup(exec_id)
                return run

            thread = threading.Thread(target=make_quant_runner(execution_id), daemon=True)
        else:
            thread = threading.Thread(target=make_background_runner(execution_id), daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'execution_id': execution_id,
            'message': '工作流已启动，可通过 SSE 订阅实时进度'
        }), 202

    except Exception as e:
        logger.error(f"Run workflow failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/execution/<execution_id>/progress', methods=['GET'])
def get_execution_progress(workflow_id, execution_id):
    """获取执行进度"""
    try:
        execution = execution_storage.get_execution(execution_id)
        if not execution or execution.workflow_id != workflow_id:
            return jsonify({'success': False, 'error': 'Execution not found'}), 404

        return jsonify({
            'success': True,
            'data': {
                'execution_id': execution.id,
                'workflow_id': execution.workflow_id,
                'status': execution.status,
                'progress': execution.progress,
                'current_node': execution.current_node,
                'current_step': execution.current_step,
                'steps': execution.steps,
                'result': execution.result,
                'error': execution.error,
                'started_at': execution.started_at,
                'finished_at': execution.finished_at
            }
        })
    except Exception as e:
        logger.error(f"Get execution progress failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/execution/<execution_id>/stream', methods=['GET'])
def stream_execution_progress(workflow_id, execution_id):
    """SSE 实时推送执行进度（替代轮询）。"""
    execution = execution_storage.get_execution(execution_id)
    if not execution or execution.workflow_id != workflow_id:
        return jsonify({'success': False, 'error': 'Execution not found'}), 404

    q = WorkflowSSE.subscribe(execution_id)

    def generate():
        try:
            while True:
                try:
                    payload = q.get(timeout=30)
                    yield payload
                    if '"status": "completed"' in payload or '"status": "failed"' in payload or '"status": "cancelled"' in payload:
                        break
                except Exception:
                    yield f"event: heartbeat\ndata: {{{{}}}}\n\n"
        finally:
            WorkflowSSE.unsubscribe(execution_id, q)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@workflow_bp.route('/<workflow_id>/execution/<execution_id>/cancel', methods=['POST'])
def cancel_execution(workflow_id, execution_id):
    """终止执行中的工作流（不可恢复）"""
    try:
        execution = execution_storage.get_execution(execution_id)
        if not execution or execution.workflow_id != workflow_id:
            return jsonify({'success': False, 'error': 'Execution not found'}), 404

        if execution.status not in [ExecutionStatus.PENDING.value, ExecutionStatus.RUNNING.value, ExecutionStatus.PAUSED.value]:
            return jsonify({'success': False, 'error': 'Execution is not running or paused'}), 400

        from modules.workflow.executor import WorkflowCancelManager, WorkflowPauseManager
        WorkflowCancelManager.cancel(execution_id)
        WorkflowPauseManager.clear(execution_id)

        execution_storage.cancel_execution(execution_id)
        return jsonify({'success': True, 'message': 'Cancel requested'})
    except Exception as e:
        logger.error(f"Cancel execution failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/execution/<execution_id>/pause', methods=['POST'])
def pause_execution_route(workflow_id, execution_id):
    """暂停执行中的工作流（节点间暂停，可继续）"""
    try:
        execution = execution_storage.get_execution(execution_id)
        if not execution or execution.workflow_id != workflow_id:
            return jsonify({'success': False, 'error': 'Execution not found'}), 404

        if execution.status not in [ExecutionStatus.PENDING.value, ExecutionStatus.RUNNING.value]:
            return jsonify({'success': False, 'error': 'Execution is not running'}), 400

        from modules.workflow.executor import WorkflowPauseManager
        WorkflowPauseManager.pause(execution_id)

        return jsonify({'success': True, 'message': '已请求暂停，将在当前步骤完成后暂停'})
    except Exception as e:
        logger.error(f"Pause execution failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/execution/<execution_id>/resume', methods=['POST'])
def resume_execution_route(workflow_id, execution_id):
    """从暂停点继续执行工作流"""
    try:
        execution = execution_storage.get_execution(execution_id)
        if not execution or execution.workflow_id != workflow_id:
            return jsonify({'success': False, 'error': 'Execution not found'}), 404

        if execution.status != ExecutionStatus.PAUSED.value:
            return jsonify({'success': False, 'error': '任务未处于暂停状态'}), 400

        workflow = workflow_storage.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404

        from modules.workflow.executor import WorkflowPauseManager
        WorkflowPauseManager.clear(execution_id)

        execution_storage.resume_execution(execution_id)

        nodes = [n.to_dict() if hasattr(n, 'to_dict') else n for n in workflow.nodes]
        edges = [e.to_dict() if hasattr(e, 'to_dict') else e for e in workflow.edges]
        start_idx = execution.paused_node_idx
        codes_override = execution.paused_codes or None

        def make_progress_callback(exec_id: str):
            def progress_callback(node_id, node_label, step, progress, detail=None):
                step_data = {
                    'node_id': node_id, 'node_label': node_label, 'step': step,
                    'progress': progress, 'detail': detail or {},
                    'timestamp': datetime.now().isoformat()
                }
                execution_storage.update_progress(exec_id, progress, node_id, step, step_data)
            return progress_callback

        def make_background_runner_resume(exec_id, start_from_idx, c_override):
            def execute_in_background():
                try:
                    from modules.workflow.executor import WorkflowExecutor as _WE
                    executor = _WE(workflow_id, exec_id, make_progress_callback(exec_id))
                    result = executor.execute(nodes, edges, {}, start_from_idx=start_from_idx, codes_override=c_override)
                    if result.get('success'):
                        execution_storage.complete_execution(exec_id, result)
                        workflow_storage.update_last_run(workflow_id)
                    elif result.get('paused'):
                        execution_storage.pause_execution(exec_id, result.get('paused_node_idx', 0), result.get('codes', []))
                    elif result.get('cancelled'):
                        execution_storage.cancel_execution(exec_id)
                    else:
                        execution_storage.fail_execution(exec_id, result.get('error', 'Unknown error'))
                except Exception as e:
                    import traceback
                    logger.error(f"Resume execution failed: {e}\n{traceback.format_exc()}")
                    execution_storage.fail_execution(exec_id, str(e))
            return execute_in_background

        thread = threading.Thread(target=make_background_runner_resume(execution_id, start_idx, codes_override), daemon=True)
        thread.start()

        return jsonify({'success': True, 'execution_id': execution_id, 'message': f'已从步骤 {start_idx + 1} 继续执行'})
    except Exception as e:
        logger.error(f"Resume execution failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/executions', methods=['GET'])
def list_executions(workflow_id):
    """获取工作流的执行历史"""
    try:
        limit = request.args.get('limit', 20, type=int)
        executions = execution_storage.list_executions(workflow_id, limit=limit)
        return jsonify({
            'success': True,
            'data': [e.to_dict() for e in executions]
        })
    except Exception as e:
        logger.error(f"List executions failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/execution/<execution_id>', methods=['DELETE'])
def delete_execution(workflow_id, execution_id):
    """删除单条执行历史"""
    try:
        execution = execution_storage.get_execution(execution_id)
        if not execution or execution.workflow_id != workflow_id:
            return jsonify({'success': False, 'error': 'Execution not found'}), 404
        if execution.status in [ExecutionStatus.PENDING.value, ExecutionStatus.RUNNING.value]:
            return jsonify({'success': False, 'error': '任务正在执行中，请先停止再删除'}), 400
        if execution_storage.delete_execution(execution_id):
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Delete failed'}), 500
    except Exception as e:
        logger.error(f"Delete execution failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/executions/batch', methods=['DELETE'])
def batch_delete_executions(workflow_id):
    """批量删除执行历史"""
    try:
        data = request.get_json() or {}
        execution_ids = data.get('execution_ids', [])
        if not execution_ids:
            return jsonify({'success': False, 'error': 'No execution IDs provided'}), 400
        deleted = execution_storage.delete_executions_batch(execution_ids)
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        logger.error(f"Batch delete executions failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/<workflow_id>/executions/all', methods=['DELETE'])
def clear_all_executions(workflow_id):
    """清空工作流所有执行历史"""
    try:
        workflow = workflow_storage.get_workflow(workflow_id)
        if not workflow:
            return jsonify({'success': False, 'error': 'Workflow not found'}), 404
        execution_storage.delete_executions(workflow_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Clear all executions failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/executions/cleanup', methods=['POST'])
def cleanup_stale_executions():
    """手动清理所有超时僵尸任务"""
    try:
        data = request.get_json() or {}
        max_age = data.get('max_age_minutes', 30)
        cleaned = execution_storage.cleanup_stale_executions(max_age_minutes=max_age)
        return jsonify({'success': True, 'cleaned': cleaned,
                        'message': f'已清理 {cleaned} 条僵尸任务'})
    except Exception as e:
        logger.error(f"Cleanup stale executions failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates', methods=['GET'])
def get_templates():
    """获取工作流模板"""
    try:
        owner_id = request.args.get('owner_id')
        category = request.args.get('category')
        tags = request.args.getlist('tags')

        templates = template_storage.list_templates(
            owner_id=owner_id,
            category=category,
            tags=tags if tags else None,
            include_public=True
        )

        return jsonify({
            'success': True,
            'data': [t.to_dict() for t in templates]
        })
    except Exception as e:
        logger.error(f"Get templates failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """获取单个模板"""
    try:
        template = template_storage.get_template(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        return jsonify({
            'success': True,
            'data': template.to_dict()
        })
    except Exception as e:
        logger.error(f"Get template failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates', methods=['POST'])
def create_template():
    """创建工作流模板"""
    try:
        data = request.get_json()
        template_id = data.get('id') or str(uuid.uuid4())

        template = WorkflowTemplate(
            id=template_id,
            name=data.get('name', 'New Template'),
            description=data.get('description', ''),
            tags=data.get('tags', []),
            nodes=[WorkflowNode.from_dict(n) if isinstance(n, dict) else n for n in data.get('nodes', [])],
            edges=[WorkflowEdge.from_dict(e) if isinstance(e, dict) else e for e in data.get('edges', [])],
            is_public=data.get('is_public', True),
            owner_id=data.get('owner_id'),
            category=data.get('category', 'custom'),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        if template_storage.save_template(template):
            return jsonify({
                'success': True,
                'data': template.to_dict()
            }), 201
        else:
            return jsonify({'success': False, 'error': 'Failed to save template'}), 500
    except Exception as e:
        logger.error(f"Create template failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates/<template_id>', methods=['PUT'])
def update_template(template_id):
    """更新工作流模板"""
    try:
        data = request.get_json()
        template = template_storage.get_template(template_id)

        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        if 'name' in data:
            template.name = data['name']
        if 'description' in data:
            template.description = data['description']
        if 'tags' in data:
            template.tags = data['tags']
        if 'nodes' in data:
            template.nodes = [WorkflowNode.from_dict(n) if isinstance(n, dict) else n for n in data['nodes']]
        if 'edges' in data:
            template.edges = [WorkflowEdge.from_dict(e) if isinstance(e, dict) else e for e in data['edges']]
        if 'is_public' in data:
            template.is_public = data['is_public']
        if 'category' in data:
            template.category = data['category']

        template.updated_at = datetime.now().isoformat()

        if template_storage.save_template(template):
            return jsonify({
                'success': True,
                'data': template.to_dict()
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save template'}), 500
    except Exception as e:
        logger.error(f"Update template failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates/<template_id>', methods=['DELETE'])
def delete_template(template_id):
    """删除工作流模板"""
    try:
        if template_storage.delete_template(template_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
    except Exception as e:
        logger.error(f"Delete template failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates/categories', methods=['GET'])
def get_template_categories():
    """获取模板分类"""
    try:
        categories = template_storage.list_categories()
        return jsonify({
            'success': True,
            'data': categories
        })
    except Exception as e:
        logger.error(f"Get categories failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/templates/tags', methods=['GET'])
def get_template_tags():
    """获取所有模板标签"""
    try:
        tags = template_storage.list_all_tags()
        return jsonify({
            'success': True,
            'data': tags
        })
    except Exception as e:
        logger.error(f"Get tags failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workflow_bp.route('/node-types', methods=['GET'])
def get_node_types():
    """获取支持的节点类型"""
    node_types = {
        'start': {
            'type': 'start',
            'label': '起始节点',
            'description': '定义工作流的起始点和数据来源',
            'icon': 'play',
            'config_schema': {
                'source': {
                    'type': 'select',
                    'label': '数据源',
                    'options': [
                        {'value': 'all', 'label': '全部股票'},
                        {'value': 'watchlist', 'label': '自选股'},
                        {'value': 'sector', 'label': '板块'}
                    ],
                    'default': 'all'
                },
                'sector': {
                    'type': 'text',
                    'label': '板块名称',
                    'show_if': {'field': 'source', 'value': 'sector'}
                }
            }
        },
        'filter': {
            'type': 'filter',
            'label': '筛选节点',
            'description': '根据条件筛选股票',
            'icon': 'filter',
            'config_schema': {
                'filter_type': {
                    'type': 'select',
                    'label': '筛选类型',
                    'options': [
                        {'value': 'price_range', 'label': '价格区间'},
                        {'value': 'volume_ratio', 'label': '成交量放大'},
                        {'value': 'pe_range', 'label': 'PE范围'},
                        {'value': 'pb_range', 'label': 'PB范围'},
                        {'value': 'trend', 'label': '趋势筛选'},
                        {'value': 'fund_flow', 'label': '资金流向'},
                        {'value': 'market_cap', 'label': '市值筛选'},
                        {'value': 'exclude_st', 'label': '排除ST股票'},
                        {'value': 'news_sentiment', 'label': '舆情筛选'},
                        {'value': 'sector', 'label': '板块筛选'}
                    ],
                    'default': 'price_range'
                },
                'min_price': {'type': 'number', 'label': '最低价', 'show_if': {'field': 'filter_type', 'value': 'price_range'}},
                'max_price': {'type': 'number', 'label': '最高价', 'show_if': {'field': 'filter_type', 'value': 'price_range'}},
                'threshold': {'type': 'number', 'label': '阈值', 'show_if': {'field': 'filter_type', 'value': ['volume_ratio', 'fund_flow']}},
                'direction': {'type': 'select', 'label': '方向', 'options': [{'value': 'positive', 'label': '正向'}, {'value': 'negative', 'label': '负向'}], 'show_if': {'field': 'filter_type', 'value': 'fund_flow'}},
                'min_pe': {'type': 'number', 'label': '最小PE', 'show_if': {'field': 'filter_type', 'value': 'pe_range'}},
                'max_pe': {'type': 'number', 'label': '最大PE', 'show_if': {'field': 'filter_type', 'value': 'pe_range'}},
                'min_pb': {'type': 'number', 'label': '最小PB', 'show_if': {'field': 'filter_type', 'value': 'pb_range'}},
                'max_pb': {'type': 'number', 'label': '最大PB', 'show_if': {'field': 'filter_type', 'value': 'pb_range'}},
                'trend_type': {'type': 'select', 'label': '趋势类型', 'options': [{'value': 'up', 'label': '上涨'}, {'value': 'down', 'label': '下跌'}], 'show_if': {'field': 'filter_type', 'value': 'trend'}},
                'min_cap': {'type': 'number', 'label': '最小市值(亿)', 'show_if': {'field': 'filter_type', 'value': 'market_cap'}},
                'max_cap': {'type': 'number', 'label': '最大市值(亿)', 'show_if': {'field': 'filter_type', 'value': 'market_cap'}},
                'min_positive_ratio': {'type': 'number', 'label': '最小正面舆情比例', 'show_if': {'field': 'filter_type', 'value': 'news_sentiment'}},
                'sector': {'type': 'text', 'label': '板块名称', 'show_if': {'field': 'filter_type', 'value': 'sector'}}
            }
        },
        'score': {
            'type': 'score',
            'label': '评分节点',
            'description': '对股票进行多维度评分',
            'icon': 'star',
            'config_schema': {
                'score_type': {
                    'type': 'select',
                    'label': '评分类型',
                    'options': [
                        {'value': 'weighted', 'label': '加权评分'},
                        {'value': 'technical', 'label': '技术面评分'},
                        {'value': 'fundamental', 'label': '基本面评分'},
                        {'value': 'fund_flow', 'label': '资金流评分'},
                        {'value': 'sentiment', 'label': '舆情评分'}
                    ],
                    'default': 'weighted'
                },
                'weights': {
                    'type': 'object',
                    'label': '评分权重',
                    'show_if': {'field': 'score_type', 'value': 'weighted'},
                    'properties': {
                        'technical': {'type': 'number', 'label': '技术面权重', 'default': 0.25},
                        'fundamental': {'type': 'number', 'label': '基本面权重', 'default': 0.25},
                        'sentiment': {'type': 'number', 'label': '舆情权重', 'default': 0.25},
                        'fund_flow': {'type': 'number', 'label': '资金流权重', 'default': 0.25}
                    }
                }
            }
        },
        'ai_agent': {
            'type': 'ai_agent',
            'label': 'AI Agent节点',
            'description': '使用AI Agent进行深度分析',
            'icon': 'robot',
            'config_schema': {
                'agent_id': {
                    'type': 'select',
                    'label': '选择Agent',
                    'options': [],
                    'load_from': '/api/v1/ai-agents'
                },
                'top_n': {'type': 'number', 'label': '分析前N只', 'default': 20}
            }
        },
        'combine': {
            'type': 'combine',
            'label': '组合节点',
            'description': '合并和优化选股结果',
            'icon': 'collection',
            'config_schema': {
                'strategy': {
                    'type': 'select',
                    'label': '组合策略',
                    'options': [
                        {'value': 'top_n', 'label': '取前N名'},
                        {'value': 'min_score', 'label': '最低分过滤'},
                        {'value': 'diversify', 'label': '分散配置'}
                    ],
                    'default': 'top_n'
                },
                'top_n': {'type': 'number', 'label': '数量', 'default': 20, 'show_if': {'field': 'strategy', 'value': ['top_n', 'min_score']}},
                'min_score': {'type': 'number', 'label': '最低分', 'default': 60, 'show_if': {'field': 'strategy', 'value': 'min_score'}}
            }
        },
        'risk_control': {
            'type': 'risk_control',
            'label': '风控节点',
            'description': '应用风险控制规则',
            'icon': 'shield',
            'config_schema': {
                'max_positions': {'type': 'number', 'label': '最大持仓数', 'default': 10},
                'max_position_ratio': {'type': 'number', 'label': '单只最大比例', 'default': 0.1},
                'exclude_st': {'type': 'boolean', 'label': '排除ST股票', 'default': True}
            }
        },
        'end': {
            'type': 'end',
            'label': '结束节点',
            'description': '输出选股结果',
            'icon': 'stop',
            'config_schema': {
                'output': {
                    'type': 'select',
                    'label': '输出类型',
                    'options': [
                        {'value': 'list', 'label': '列表'},
                        {'value': 'export', 'label': '导出'}
                    ],
                    'default': 'list'
                },
                'top_n': {'type': 'number', 'label': '输出数量', 'default': 10}
            }
        },
        'data_fetch': {
            'type': 'data_fetch',
            'label': '数据获取节点',
            'description': '从多种数据源获取股票数据',
            'icon': 'database',
            'config_schema': {
                'data_type': {
                    'type': 'select',
                    'label': '数据类型',
                    'options': [
                        {'value': 'kline', 'label': 'K线数据'},
                        {'value': 'realtime', 'label': '实时行情'},
                        {'value': 'financial', 'label': '财务数据'},
                        {'value': 'fund_flow', 'label': '资金流向'},
                        {'value': 'sentiment', 'label': '舆情数据'},
                        {'value': 'dragon_tiger', 'label': '龙虎榜'},
                        {'value': 'margin', 'label': '融资融券'},
                        {'value': 'signals', 'label': '交易信号'}
                    ],
                    'default': 'kline'
                },
                'days': {'type': 'number', 'label': '历史天数', 'default': 60, 'show_if': {'field': 'data_type', 'value': ['kline', 'sentiment']}},
                'limit': {'type': 'number', 'label': '数据条数', 'default': 100}
            }
        },
        'technical_indicator': {
            'type': 'technical_indicator',
            'label': '技术指标节点',
            'description': '计算技术分析指标',
            'icon': 'line-chart',
            'config_schema': {
                'indicator_type': {
                    'type': 'select',
                    'label': '指标类型',
                    'options': [
                        {'value': 'ma', 'label': '均线(MA)'},
                        {'value': 'ema', 'label': '指数均线(EMA)'},
                        {'value': 'macd', 'label': 'MACD'},
                        {'value': 'kdj', 'label': 'KDJ'},
                        {'value': 'rsi', 'label': 'RSI'},
                        {'value': 'boll', 'label': '布林带(BOLL)'},
                        {'value': 'volume', 'label': '成交量指标'}
                    ],
                    'default': 'ma'
                },
                'params': {
                    'type': 'text',
                    'label': '参数配置',
                    'placeholder': '如: 5,20,60',
                    'show_if': {'field': 'indicator_type', 'value': ['ma', 'ema']}
                }
            }
        },
        'fundamental_filter': {
            'type': 'fundamental_filter',
            'label': '基本面筛选节点',
            'description': '基于财务指标进行筛选',
            'icon': 'reading',
            'config_schema': {
                'filter_type': {
                    'type': 'select',
                    'label': '财务指标',
                    'options': [
                        {'value': 'pe', 'label': '市盈率(PE)'},
                        {'value': 'pb', 'label': '市净率(PB)'},
                        {'value': 'roe', 'label': '净资产收益率(ROE)'},
                        {'value': 'revenue_growth', 'label': '营收增长率'},
                        {'value': 'profit_growth', 'label': '净利润增长率'},
                        {'value': 'gross_margin', 'label': '毛利率'},
                        {'value': 'net_margin', 'label': '净利率'},
                        {'value': 'debt_ratio', 'label': '资产负债率'}
                    ],
                    'default': 'pe'
                },
                'operator': {
                    'type': 'select',
                    'label': '比较运算符',
                    'options': [
                        {'value': 'gt', 'label': '大于'},
                        {'value': 'lt', 'label': '小于'},
                        {'value': 'between', 'label': '区间'}
                    ],
                    'default': 'lt'
                },
                'value': {'type': 'number', 'label': '阈值'},
                'min_value': {'type': 'number', 'label': '最小值', 'show_if': {'field': 'operator', 'value': 'between'}},
                'max_value': {'type': 'number', 'label': '最大值', 'show_if': {'field': 'operator', 'value': 'between'}}
            }
        },
        'market_sentiment': {
            'type': 'market_sentiment',
            'label': '市场情绪节点',
            'description': '分析市场整体情绪和热点',
            'icon': 'chat-line-square',
            'config_schema': {
                'analysis_type': {
                    'type': 'select',
                    'label': '分析类型',
                    'options': [
                        {'value': 'overall', 'label': '整体情绪'},
                        {'value': 'hot_sectors', 'label': '热点板块'},
                        {'value': 'capital_flow', 'label': '资金流向'},
                        {'value': 'news_impact', 'label': '新闻影响'}
                    ],
                    'default': 'overall'
                },
                'threshold': {'type': 'number', 'label': '情绪阈值', 'default': 50}
            }
        },
        'index_components': {
            'type': 'index_components',
            'label': '指数成分节点',
            'description': '获取指定指数的成分股',
            'icon': 'collection',
            'config_schema': {
                'index_code': {
                    'type': 'select',
                    'label': '指数',
                    'options': [
                        {'value': '000300.sh', 'label': '沪深300'},
                        {'value': '000905.sh', 'label': '中证500'},
                        {'value': '000001.sh', 'label': '上证指数'},
                        {'value': '399001.sz', 'label': '深证成指'},
                        {'value': '399006.sz', 'label': '创业板指'}
                    ],
                    'default': '000300.sh'
                }
            }
        },
        'compare': {
            'type': 'compare',
            'label': '对比分析节点',
            'description': '对比多只股票的指标数据',
            'icon': 'data-analysis',
            'config_schema': {
                'compare_type': {
                    'type': 'select',
                    'label': '对比维度',
                    'options': [
                        {'value': 'price', 'label': '价格对比'},
                        {'value': 'performance', 'label': '涨跌幅对比'},
                        {'value': 'valuation', 'label': '估值对比'},
                        {'value': 'fund_flow', 'label': '资金流向对比'}
                    ],
                    'default': 'performance'
                },
                'ranking': {
                    'type': 'select',
                    'label': '排序方式',
                    'options': [
                        {'value': 'asc', 'label': '升序'},
                        {'value': 'desc', 'label': '降序'}
                    ],
                    'default': 'desc'
                }
            }
        }
    }

    return jsonify({
        'success': True,
        'data': node_types
    })
