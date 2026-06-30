# metrics_collector.py
"""
Сборщик метрик для профилирования детектора.
Минимальные зависимости, вывод в JSON для агрегации.

"""


from datetime import datetime, timezone
import time
import psutil
import os
import json
from datetime import datetime
from typing import Dict, Optional
import tracemalloc  # встроенный, для точного замера памяти объектов

class MetricsCollector:
    def __init__(self, user_id: str = "default", output_file: str = "metrics_log.jsonl"):
        self.user_id = user_id
        self.output_file = output_file
        self.process = psutil.Process(os.getpid())
        self.stage_timings: Dict[str, float] = {}
        self.stage_starts: Dict[str, float] = {}
        
        # Для детального анализа памяти
        tracemalloc.start()
        
        # Базовые метрики процесса
        self.base_cpu_count = psutil.cpu_count(logical=True)
        self.base_mem_total = psutil.virtual_memory().total
        
    def start_stage(self, stage_name: str):
        """Начать замер этапа"""
        self.stage_starts[stage_name] = time.perf_counter()
        
    def end_stage(self, stage_name: str) -> float:
        """Завершить замер этапа, вернуть длительность в секундах"""
        if stage_name in self.stage_starts:
            duration = time.perf_counter() - self.stage_starts[stage_name]
            self.stage_timings[stage_name] = duration
            return duration
        return 0.0
    
    def get_process_metrics(self) -> Dict:
        """Снять текущие метрики процесса"""
        mem_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=None)
        
        # Memory breakdown
        current, peak = tracemalloc.get_traced_memory()
        
        return {
            "rss_mb": round(mem_info.rss / 1024 / 1024, 2),      # Реальная память в RAM
            "vms_mb": round(mem_info.vms / 1024 / 1024, 2),      # Виртуальная память
            "cpu_percent": cpu_percent,                           # Загрузка CPU %
            "cpu_threads": self.process.num_threads(),            # Количество потоков
            "mem_tracemalloc_current_mb": round(current / 1024 / 1024, 2),
            "mem_tracemalloc_peak_mb": round(peak / 1024 / 1024, 2),
        }
    
    def collect_iteration_metrics(self, iteration: int, 
                                  detection_result: Dict,
                                  extra: Optional[Dict] = None) -> Dict:
        """Собрать полный срез метрик за итерацию"""
        proc_metrics = self.get_process_metrics()
        
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(), 
	  # "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": self.user_id,
            "iteration": iteration,
            
            # Тайминги этапов
            "timing_total_sec": round(sum(self.stage_timings.values()), 3),
            "timings": {k: round(v, 3) for k, v in self.stage_timings.items()},
            
            # Ресурсы процесса
            "resources": proc_metrics,
            
            # Бизнес-метрики (результат детекции)
            "detection": detection_result,
            
            # Системная информация для масштабирования
            "system": {
                "cpu_logical_cores": self.base_cpu_count,
                "mem_total_gb": round(self.base_mem_total / 1024**3, 2),
                "load_avg_1min": os.getloadavg()[0] if hasattr(os, 'getloadavg') else None,
            },
        }
        
        if extra:
            metrics["extra"] = extra
            
        # Сброс таймингов для следующей итерации
        self.stage_timings.clear()
        
        return metrics
    
    def log_metrics(self, metrics: Dict):
        """Записать метрики в JSONL файл (одна строка = одна итерация)"""
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(metrics, ensure_ascii=False) + "\n")
    
    def reset_memory_tracking(self):
        """Сбросить трекер памяти для чистого замера следующей итерации"""
        tracemalloc.stop()
        tracemalloc.start()
    
    def close(self):
        """Завершить сбор метрик"""
        tracemalloc.stop()
