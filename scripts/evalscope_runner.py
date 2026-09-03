#!/usr/bin/env python3
"""Run EvalScope without placing an API key in a file or command line."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def emit(event: str, **payload: object) -> None:
    print(json.dumps({'event': event, **payload}, ensure_ascii=False), flush=True)


def main() -> int:
    if len(sys.argv) != 2:
        emit('error', message='runner requires a JSON job file')
        return 2

    job_path = Path(sys.argv[1]).resolve()
    try:
        job = json.loads(job_path.read_text(encoding='utf-8'))
    except Exception as exc:
        emit('error', message=f'cannot read job configuration: {exc}')
        return 2

    api_key = os.environ.get('LLM_INTEGRITY_EVAL_API_KEY', '')
    if not api_key:
        emit('error', message='API key was not supplied through the runtime environment')
        return 2

    try:
        from evalscope import run_task
        from evalscope.config import TaskConfig
    except ImportError:
        emit('error', message='EvalScope is not installed; run the capability installation script first')
        return 3

    output_dir = Path(job['work_dir']).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = list(job['datasets'])
    emit('started', datasets=datasets, model=job['model'], limit=job['limit'])

    config = TaskConfig(
        model=job['model'],
        model_id=job['model'],
        datasets=datasets,
        eval_type=job.get('eval_type', 'openai_api'),
        api_url=job['api_url'],
        api_key=api_key,
        limit=job['limit'],
        eval_batch_size=job['concurrency'],
        work_dir=str(output_dir),
        collect_perf=True,
        ignore_errors=True,
        debug=False,
        generation_config={
            'temperature': 0.0,
            'max_tokens': job.get('max_tokens', 2048),
            'timeout': job.get('timeout', 120),
        },
    )

    try:
        run_task(config)
        emit('completed', datasets=datasets, output_dir=str(config.work_dir))
        return 0
    except Exception as exc:
        emit('error', message=str(exc), output_dir=str(config.work_dir))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
