import time
import threading


class SnowflakeIdGenerator:
    """
    雪花ID生成器

    位数分配:
    - 1位符号位，始终为0
    - 41位时间戳（毫秒级）
    - 10位工作机器ID（5位数据中心ID + 5位机器ID）
    - 12位序列号（同一毫秒内的计数器）
    """

    def __init__(self, datacenter_id=0, worker_id=0, epoch=1735660800000):  # 2021-01-01 作为默认起始时间戳
        """
        初始化雪花ID生成器

        Args:
            datacenter_id: 数据中心ID (0-31)
            worker_id: 工作机器ID (0-31)
            epoch: 起始时间戳，单位毫秒，默认为2021-01-01
        """
        # 位数限制
        self.WORKER_ID_BITS = 5
        self.DATACENTER_ID_BITS = 5
        self.SEQUENCE_BITS = 12

        # 最大值
        self.MAX_WORKER_ID = -1 ^ (-1 << self.WORKER_ID_BITS)
        self.MAX_DATACENTER_ID = -1 ^ (-1 << self.DATACENTER_ID_BITS)
        self.MAX_SEQUENCE = -1 ^ (-1 << self.SEQUENCE_BITS)

        # 位移
        self.WORKER_ID_SHIFT = self.SEQUENCE_BITS
        self.DATACENTER_ID_SHIFT = self.SEQUENCE_BITS + self.WORKER_ID_BITS
        self.TIMESTAMP_SHIFT = self.SEQUENCE_BITS + self.WORKER_ID_BITS + self.DATACENTER_ID_BITS

        # 参数验证
        if worker_id > self.MAX_WORKER_ID or worker_id < 0:
            raise ValueError(f"Worker ID不能大于{self.MAX_WORKER_ID}或小于0")

        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError(f"Datacenter ID不能大于{self.MAX_DATACENTER_ID}或小于0")

        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.epoch = epoch

        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    def _next_millis(self, last_timestamp):
        """获取下一毫秒时间戳"""
        timestamp = self._get_time()
        while timestamp <= last_timestamp:
            timestamp = self._get_time()
        return timestamp

    def _get_time(self):
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)

    def generate_id(self):
        """
        生成下一个ID

        Returns:
            生成的雪花ID
        """
        with self.lock:
            current_timestamp = self._get_time()

            # 时钟回拨检查
            if current_timestamp < self.last_timestamp:
                raise RuntimeError(f"时钟回拨，拒绝生成ID，回拨时间: {self.last_timestamp - current_timestamp}毫秒")

            # 同一毫秒内
            if current_timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                # 同一毫秒内序列号用尽
                if self.sequence == 0:
                    current_timestamp = self._next_millis(self.last_timestamp)
            else:
                # 不同毫秒，序列号重置
                self.sequence = 0

            self.last_timestamp = current_timestamp

            # 生成ID (时间戳部分 | 数据中心部分 | 机器ID部分 | 序列号部分)
            snowflake_id = ((current_timestamp - self.epoch) << self.TIMESTAMP_SHIFT) | \
                           (self.datacenter_id << self.DATACENTER_ID_SHIFT) | \
                           (self.worker_id << self.WORKER_ID_SHIFT) | \
                           self.sequence

            return snowflake_id


# 使用示例
if __name__ == "__main__":
    # 创建ID生成器实例，指定数据中心ID和工作机器ID
    id_generator = SnowflakeIdGenerator(datacenter_id=1, worker_id=1)

    # 生成10个ID
    ids = [id_generator.generate_id() for _ in range(10)]

    # 打印生成的ID
    for i, id_val in enumerate(ids):
        print(f"ID {i + 1}: {id_val}")

    # 验证ID唯一性
    print(f"生成ID数量: {len(ids)}")
    print(f"唯一ID数量: {len(set(ids))}")