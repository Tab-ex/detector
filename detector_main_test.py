import time
import numpy as np
import sys
import os
import glob
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from recorder_ram import record_5s_to_ram
from moped_ml_detector import MopedFeatureExtractor, MopedMLDetector
from metrics_collector import MetricsCollector
from hat_mesh.result_sender import ResultSender
from config import (
    CONFIDENCE_THRESHOLD,
    LOOP_DELAY,
    SAMPLE_RATE,
    WINDOW_SIZE,
    METRICS_ENABLED,
    METRICS_USER_ID,
    METRICS_FILE,
    HAT,
    MESH_CMD_ENABLED,
)

# Вместо MODEL_PATH
pkl_files = glob.glob("*.pkl")
MODEL_PATH = pkl_files[0] if pkl_files else None

def _start_mesh_command_listener(result_sender: ResultSender):
    if not HAT or not MESH_CMD_ENABLED or result_sender.mesh_sender is None:
        return None
    from hat_mesh.meshtastic_command_listener import MeshtasticCommandListener

    listener = MeshtasticCommandListener(result_sender.mesh_sender)
    listener.start()
    return listener


def _shutdown(metrics, cmd_listener, result_sender) -> None:
    if cmd_listener is not None:
        cmd_listener.stop()
    if metrics is not None:
        metrics.close()
    result_sender.close()


def main():
    print(" Инициализация компонентов...")

    metrics = MetricsCollector(
        user_id=METRICS_USER_ID,
        output_file=METRICS_FILE,
    ) if METRICS_ENABLED else None

    result_sender = ResultSender()
    cmd_listener = None

    if HAT:
        print(" HAT=true: Meshtastic + датчики, команды в фоне")
        cmd_listener = _start_mesh_command_listener(result_sender)
    else:
        print(" HAT=false: MQTT, без Meshtastic и датчиков")

    model_load_start = time.perf_counter()
    if MODEL_PATH:
        detector = MopedMLDetector(model_path=MODEL_PATH)
    else:
        print("Ошибка: .pkl файлы не найдены в текущей папке")
    if not detector.load_model():
        print(" Не удалось загрузить модель. Проверьте наличие my_model_1.pkl")
        _shutdown(metrics, cmd_listener, result_sender)
        sys.exit(1)
    model_load_time = time.perf_counter() - model_load_start
    print(f" Модель загружена за {model_load_time:.2f} сек")

    extractor = MopedFeatureExtractor(sample_rate=SAMPLE_RATE, window_size=WINDOW_SIZE)

    print(" Компоненты готовы. Запуск цикла...")
    print(" Для остановки нажмите Ctrl+C\n")

    iteration = 0
    try:
        while True:
            iteration += 1

            if metrics:
                metrics.reset_memory_tracking()
                _ = metrics.process.cpu_percent(interval=None)

            print(f" Цикл #{iteration} | Запись 5 сек в RAM...")

            if metrics:
                metrics.start_stage("record")
            audio_data, sr = record_5s_to_ram()
            if metrics:
                metrics.end_stage("record")

            if audio_data is None:
                print(" Ошибка записи, пропуск...")
                time.sleep(LOOP_DELAY)
                continue

            if metrics:
                metrics.start_stage("feature_extraction")

            window_samples = int(WINDOW_SIZE * sr)
            moped_windows = 0
            max_conf = 0.0
            predictions = []

            for i in range(0, len(audio_data) - window_samples, window_samples):
                chunk = audio_data[i:i + window_samples]
                features = extractor.extract_features(chunk)

                if features:
                    if metrics:
                        metrics.start_stage("predict_single")
                    is_moped, conf = detector.predict(features, threshold=CONFIDENCE_THRESHOLD)
                    if metrics:
                        metrics.end_stage("predict_single")

                    predictions.append(conf)
                    if is_moped:
                        moped_windows += 1
                    if conf > max_conf:
                        max_conf = conf

            if metrics:
                metrics.end_stage("feature_extraction")

            avg_conf = float(np.mean(predictions)) if predictions else 0.0
            is_detected = moped_windows > 0
            status = "DETECTED" if is_detected else "CLEAN"

            print(
                f" Результат: {status} | MaxConf: {max_conf:.3f} | "
                f"AvgConf: {avg_conf:.3f} | OK: {moped_windows}/5"
            )

            if metrics:
                metrics.start_stage("send_network")

            payload = {
                "iteration": iteration,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": status,
                "moped_detected": is_detected,
                "confidence_avg": round(avg_conf, 4),
                "confidence_max": round(max_conf, 4),
                "positive_windows": moped_windows,
                "total_windows": len(predictions),
            }
            result_sender.send(payload, is_detected)

            if metrics:
                metrics.end_stage("send_network")

            if metrics:
                detection_info = {
                    "status": status,
                    "avg_confidence": avg_conf,
                    "max_confidence": max_conf,
                    "positive_windows": moped_windows,
                }

                iteration_metrics = metrics.collect_iteration_metrics(
                    iteration=iteration,
                    detection_result=detection_info,
                    extra={
                        "audio_duration_sec": len(audio_data) / sr if sr else 0,
                        "windows_processed": len(predictions),
                    },
                )
                metrics.log_metrics(iteration_metrics)

                res = iteration_metrics["resources"]
                print(
                    f"    Metrics: CPU:{res['cpu_percent']:.1f}% | "
                    f"RAM:{res['rss_mb']:.0f}MB | "
                    f"Total:{iteration_metrics['timing_total_sec']:.2f}s"
                )

            del audio_data, predictions
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\n Детектор остановлен пользователем.")
        if metrics:
            print(f" Метрики сохранены в {METRICS_FILE}")
        _shutdown(metrics, cmd_listener, result_sender)
        sys.exit(0)

    except Exception:
        _shutdown(metrics, cmd_listener, result_sender)
        raise


if __name__ == "__main__":
    main()
