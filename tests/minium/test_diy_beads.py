import time

import minium

__test__ = False


WORKSPACE_PATH = "/pages/workspace/workspace"
CHECKOUT_PATH = "/pages/checkout/checkout"
TARGET_CATEGORY = "白水晶"
TARGET_NAME = "喜马拉雅白水晶"
TARGET_SIZE_TEXT = "12mm"
TARGET_UNIT_PRICE = 15
ADD_COUNT = 3


class TestDIYBeads(minium.MiniTest):
    """宇涧 DIY 工作台核心流程自动化测试。"""

    def wait_until(self, predicate, message, timeout=12, interval=0.25):
        deadline = time.time() + timeout
        last_error = None
        while time.time() < deadline:
            try:
                if predicate():
                    return
            except Exception as error:  # 页面切换或动画期间允许短暂读取失败
                last_error = error
            time.sleep(interval)
        detail = f"；最后一次错误：{last_error}" if last_error else ""
        self.fail(f"{message}{detail}")

    def workspace_data(self):
        return self.page.data

    def summary(self):
        return self.workspace_data().get("summary", {})

    def open_clean_workspace(self):
        print("[1] 进入 DIY 工作台并清空历史设计")
        self.app.switch_tab(WORKSPACE_PATH)
        self.page = self.app.get_current_page()
        self.assertEqual(self.page.path, WORKSPACE_PATH, "未进入 DIY 工作台")
        self.page.wait_for(".material-drawer", max_timeout=15)

        # 直接调用页面方法，避免历史草稿影响颗数与价格断言。
        self.page.call_method("clearDesign")
        self.wait_until(
            lambda: self.summary().get("count") == 0,
            "工作台未能清空",
        )

    def select_clear_quartz_category(self):
        print("[2] 选择“白水晶”分类")
        category = self.page.get_element(
            ".category-item",
            inner_text=TARGET_CATEGORY,
            max_timeout=10,
        )
        category.click()
        self.wait_until(
            lambda: self.workspace_data().get("activeCategory") == TARGET_CATEGORY,
            "白水晶分类未生效",
        )

    def find_target_material(self):
        print(f"[3] 定位材料：{TARGET_NAME} {TARGET_SIZE_TEXT}")
        cards = self.page.get_elements(
            ".material-card",
            text_contains=TARGET_NAME,
            max_timeout=10,
        )
        for card in cards:
            text = card.inner_text.replace(" ", "")
            if TARGET_SIZE_TEXT in text:
                return card
        self.fail(f"未找到材料：{TARGET_NAME} {TARGET_SIZE_TEXT}")

    def add_target_materials(self, card):
        print(f"[4] 连续添加 {ADD_COUNT} 颗珠子，并等待每次弹射完成")
        for expected_count in range(1, ADD_COUNT + 1):
            card.click()
            self.wait_until(
                lambda count=expected_count: self.summary().get("count") == count,
                f"第 {expected_count} 颗珠子未成功加入",
                timeout=15,
            )

    def assert_workspace_summary(self):
        print("[5] 校验颗数、价格以及盘面珠子数量")
        summary = self.summary()
        expected_price = TARGET_UNIT_PRICE * ADD_COUNT

        self.assertEqual(summary.get("count"), ADD_COUNT, "珠子数量计算错误")
        self.assertEqual(summary.get("price"), expected_price, "方案总价计算错误")
        self.assertEqual(
            summary.get("priceText"),
            f"{expected_price:.2f}",
            "方案价格文本格式错误",
        )

        count_badge = self.page.get_element(".count-badge")
        price = self.page.get_element(".checkout-price")
        beads = self.page.get_elements(".circle-bead")

        self.assertIn(f"{ADD_COUNT}/18", count_badge.inner_text, "顶部颗数展示错误")
        self.assertEqual(price.inner_text, f"¥{expected_price:.2f}", "底部价格展示错误")
        self.assertEqual(len(beads), ADD_COUNT, "圆盘实际渲染珠子数量错误")

    def finish_customization(self):
        print("[6] 点击“完成定制”，校验进入结算页")
        self.page.get_element(
            ".finish-btn",
            text_contains="完成定制",
            max_timeout=10,
        ).click()
        self.wait_until(
            lambda: self.app.get_current_page().path == CHECKOUT_PATH,
            "点击完成定制后未进入结算页",
            timeout=15,
        )
        self.assertEqual(self.app.get_current_page().path, CHECKOUT_PATH)

    def test_add_beads_and_check_price(self):
        self.open_clean_workspace()
        self.select_clear_quartz_category()
        material_card = self.find_target_material()
        self.add_target_materials(material_card)
        self.assert_workspace_summary()
        screenshot = self.capture("diy_3_clear_quartz_12mm")
        print(f"[证据] 截图：{screenshot}")
        self.finish_customization()
        print("[测试通过] DIY 添加珠子、计价和结算跳转均正常")
