import json
import time

import minium


HOME = "/pages/home/home"
PROFILE = "/pages/profile/profile"
ASSESSMENT = "/pages/assessment/assessment"
WORKSPACE = "/pages/workspace/workspace"
CART = "/pages/inspiration-cart/inspiration-cart"
ORDER_LIST = "/pages/order-list/order-list"
CHECKOUT = "/pages/checkout/checkout"
REPORT = "/pages/report/report"


class TestCodexFeatureSmoke(minium.MiniTest):
    """End-to-end smoke coverage for the mini-program in WeChat DevTools."""

    def setUp(self):
        self.steps = []
        self.evidence = []

    def record(self, name, status="PASS", detail=""):
        row = {"name": name, "status": status, "detail": detail}
        self.steps.append(row)
        print("[CODEX_STEP] " + json.dumps(row, ensure_ascii=False))

    def run_section(self, name, callback):
        try:
            callback()
        except Exception as error:
            self.record(name, "ERROR", str(error))
            self.screenshot("error_" + name.replace(" ", "_").replace("/", "_"))

    def current_page(self):
        return self.app.get_current_page()

    def norm(self, path):
        return (path or "").lstrip("/")

    def wait_until(self, predicate, message, timeout=20, interval=0.3):
        deadline = time.time() + timeout
        last_error = None
        while time.time() < deadline:
            try:
                if predicate():
                    return True
            except Exception as error:
                last_error = error
            time.sleep(interval)
        detail = f"; last error: {last_error}" if last_error else ""
        self.fail(f"{message}{detail}")

    def wait_path(self, path, timeout=15):
        expected = self.norm(path)
        self.wait_until(
            lambda: self.norm(self.current_page().path) == expected,
            f"Expected route {expected}, got {self.current_page().path}",
            timeout=timeout,
        )
        return self.current_page()

    def switch_tab(self, path, timeout=18):
        self.app.switch_tab(path)
        return self.wait_path(path, timeout)

    def navigate_to(self, path, timeout=18):
        self.app.navigate_to(path)
        return self.wait_path(path, timeout)

    def screenshot(self, name):
        try:
            path = self.capture(name)
            self.evidence.append(path)
            print(f"[CODEX_SCREENSHOT] {name}: {path}")
            return path
        except Exception as error:
            self.record(f"screenshot:{name}", "WARN", str(error))
            return ""

    def page_eval(self, page, body, args=None):
        result = self.app._evaluate(body, args=args or [], sync=True)
        return (result.get("result") or {}).get("result")

    def ensure_login(self):
        page = self.switch_tab(PROFILE)
        page.wait_for(".profile-page", max_timeout=15)
        if not page.data.get("isLoggedIn"):
            page.call_method("loginWithWechat")
            self.wait_until(
                lambda: bool(self.current_page().data.get("isLoggedIn")),
                "Profile did not enter logged-in state",
                timeout=25,
            )
        user = self.current_page().data.get("user") or {}
        self.assertTrue(user.get("user_id"), "Logged-in user_id missing")
        self.screenshot("01_profile_logged_in")
        self.record("profile login", detail=f"user_id={user.get('user_id')}")
        return user

    def test_full_user_journey(self):
        user = self.ensure_login()
        self.run_section("home and inspiration", self.verify_home_and_inspiration)
        self.run_section("profile favorites entry", self.verify_favorites_entry)
        self.run_section("assessment report and recommendation", self.verify_assessment_report_and_recommendation)
        self.run_section("workspace cart checkout and orders", lambda: self.verify_workspace_cart_checkout_and_orders(user))
        print("[CODEX_SUMMARY] " + json.dumps({
            "steps": self.steps,
            "evidence": self.evidence,
        }, ensure_ascii=False))

    def verify_home_and_inspiration(self):
        page = self.switch_tab(HOME)
        page.wait_for(".hero-swiper", max_timeout=15)
        self.wait_until(
            lambda: len(self.current_page().data.get("homeBanners") or []) > 0,
            "Home banners did not load",
            timeout=18,
        )
        self.wait_until(
            lambda: len(self.current_page().data.get("inspirations") or []) > 0,
            "Home inspirations did not load",
            timeout=18,
        )
        data = self.current_page().data
        self.screenshot("02_home")
        self.record(
            "home content",
            detail=f"banners={len(data.get('homeBanners') or [])}, inspirations={len(data.get('inspirations') or [])}",
        )

        page.get_element(".plan-card", max_timeout=10).click()
        detail = self.wait_path("/pages/community-detail/community-detail", timeout=18)
        self.wait_until(
            lambda: bool(self.current_page().data.get("viewPost")),
            "Community detail did not load post data",
            timeout=18,
        )
        view_post = self.current_page().data.get("viewPost") or {}
        self.assertTrue(view_post.get("title"), "Community detail title missing")
        self.assertTrue(
            view_post.get("imageUrl") or view_post.get("visualBeads"),
            "Community detail visual missing",
        )
        self.screenshot("03_community_detail")
        self.record(
            "home inspiration opens detail",
            detail=f"title={view_post.get('title')}, materials={len(view_post.get('materials') or [])}",
        )

        before_text = detail.data.get("favoriteText")
        if before_text and "已收藏" not in before_text:
            detail.call_method("toggleFavorite")
            self.wait_until(
                lambda: self.current_page().data.get("favoriteText") != before_text,
                "Favorite state did not change",
                timeout=15,
            )
            self.record("community favorite toggle", detail=f"{before_text} -> {self.current_page().data.get('favoriteText')}")
        else:
            self.record("community favorite toggle", detail=f"already saved: {before_text}")
        self.screenshot("04_favorite_saved")

    def verify_favorites_entry(self):
        page = self.switch_tab(PROFILE)
        page.call_method("viewCommunityFavorites")
        fav = self.wait_path("/pages/community-favorites/community-favorites", timeout=15)
        self.wait_until(lambda: not self.current_page().data.get("loading"), "Favorites page still loading", timeout=18)
        posts = self.current_page().data.get("posts") or []
        if not posts:
            self.screenshot("05_favorites_page_empty_after_save")
            self.record("profile favorites entry", "FAIL", "favorite saved from detail is not visible in favorites page")
            return
        self.assertTrue(posts[0].get("imageUrl") or posts[0].get("visualBeads"), "Favorite card visual missing")
        self.screenshot("05_favorites_page")
        self.record("profile favorites entry", detail=f"favorites={len(posts)}")

        # Clean up the favorite created by this test when possible.
        first_id = posts[0].get("id")
        if first_id:
            fav.call_method("removeFavoriteFromServer", [first_id])
            self.wait_until(
                lambda: all((item.get("id") != first_id) for item in (self.current_page().data.get("posts") or [])),
                "Created favorite was not removed",
                timeout=15,
            )
            self.record("favorites cleanup", detail=f"removed={first_id}")

    def inject_assessment_form(self, page):
        data = page.data
        wish = (data.get("wishOptions") or [{}])[0].get("value")
        mbti = (data.get("mbtiOptions") or [{}])[0].get("value")
        chakra = (data.get("chakraOptions") or [{}])[0].get("value")
        palette = (data.get("moodPalettes") or [{}])[0].get("value")
        payload = {
            "currentStepIndex": 0,
            "form.name": "Codex Tester",
            "form.gender": "female",
            "form.birthDate": "1995-06-15",
            "form.birthTime": "09:30",
            "form.birthTimeUnknown": False,
            "form.birthRegion": ["重庆市", "重庆市", "渝中区"],
            "form.birthPlace": "重庆市",
            "form.mbti": mbti or "",
            "form.wishes": [wish] if wish else [],
            "form.chakraAnswers": [chakra] if chakra else [],
            "form.moodPaletteId": palette or "",
        }
        self.page_eval(
            page,
            "function(payload){var p=getCurrentPages().pop();p.setData(payload);"
            "if(p.refreshOptionState){p.refreshOptionState();}"
            "return {step:p.data.currentStepIndex, form:p.data.form};}",
            args=[payload],
        )
        self.wait_until(lambda: self.current_page().data.get("form", {}).get("name") == "Codex Tester", "Assessment form injection failed")

    def verify_assessment_report_and_recommendation(self):
        page = self.switch_tab(ASSESSMENT)
        page.wait_for(".assessment-page", max_timeout=15)
        self.inject_assessment_form(page)
        self.screenshot("06_assessment_basic")
        step_count = len(self.current_page().data.get("steps") or [])
        self.assertGreaterEqual(step_count, 5, "Assessment flow has too few steps")
        for index in range(step_count - 1):
            current = self.current_page()
            current.call_method("handlePrimaryAction")
            self.wait_until(
                lambda expected=index + 1: self.current_page().data.get("currentStepIndex") == expected,
                f"Assessment did not move to step {index + 1}",
                timeout=10,
            )
        self.screenshot("07_assessment_review")
        self.current_page().call_method("handlePrimaryAction")
        report = self.wait_path(REPORT, timeout=35)
        report.wait_for(".result-page", max_timeout=20)
        self.wait_until(lambda: bool(self.current_page().data.get("report")), "Energy report missing", timeout=20)
        view_report = self.current_page().data.get("viewReport") or {}
        self.assertTrue(view_report.get("elements"), "Report elements missing")
        self.assertTrue(view_report.get("bazi"), "Report bazi section missing")
        self.assertTrue(view_report.get("chakra"), "Report chakra section missing")
        self.assertTrue(view_report.get("mood"), "Report mood section missing")
        self.screenshot("08_report")
        self.record(
            "assessment report",
            detail=f"score={view_report.get('score')}, elements={len(view_report.get('elements') or [])}",
        )

        report.call_method("shareReport")
        self.wait_until(
            lambda: bool(self.current_page().data.get("posterPath")) and self.current_page().data.get("showPosterModal"),
            "Report poster was not generated",
            timeout=30,
        )
        self.screenshot("09_report_poster")
        self.record("report poster", detail=self.current_page().data.get("posterPath", ""))
        self.current_page().call_method("closePosterModal")

        self.current_page().call_method("openWristModal")
        self.wait_until(lambda: bool(self.current_page().data.get("showWristModal")), "Wrist modal did not open", timeout=8)
        self.screenshot("10_report_wrist_modal")
        self.current_page().call_method("confirmWristAndRecommend")
        self.wait_path(WORKSPACE, timeout=40)
        self.wait_until(
            lambda: len(self.current_page().data.get("selected") or []) > 0,
            "Recommended design did not enter workspace",
            timeout=25,
        )
        self.screenshot("11_workspace_recommended")
        self.record("report recommendation to workspace", detail=f"count={len(self.current_page().data.get('selected') or [])}")

    def verify_workspace_cart_checkout_and_orders(self, user):
        page = self.wait_path(WORKSPACE, timeout=10)
        page.wait_for(".material-drawer", max_timeout=20)
        page.call_method("clearDesign")
        self.wait_until(lambda: (self.current_page().data.get("summary") or {}).get("count") == 0, "Workspace did not clear", timeout=10)
        self.wait_until(
            lambda: len(self.current_page().data.get("visibleMaterials") or []) > 0,
            "Workspace visible materials did not load",
            timeout=25,
        )
        first_material = (self.current_page().data.get("visibleMaterials") or [{}])[0]
        self.current_page().get_element(".material-card", max_timeout=15).click()
        self.wait_until(
            lambda: (self.current_page().data.get("summary") or {}).get("count", 0) >= 1,
            "Adding a material did not update workspace summary",
            timeout=18,
        )
        summary = self.current_page().data.get("summary") or {}
        self.assertGreaterEqual(summary.get("price", 0), 0, "Workspace price is invalid")
        self.screenshot("12_workspace_added_bead")
        self.record(
            "workspace add bead",
            detail=f"material={first_material.get('name')} {first_material.get('size')}mm, count={summary.get('count')}",
        )

        self.current_page().call_method("toggleEnergyPanel")
        self.wait_until(lambda: bool(self.current_page().data.get("showEnergyPanel")), "Workspace energy panel did not open", timeout=8)
        self.current_page().call_method("openEnergyModal")
        self.wait_until(lambda: bool(self.current_page().data.get("showEnergyModal")), "Workspace energy modal did not open", timeout=8)
        self.screenshot("13_workspace_energy_modal")
        self.current_page().call_method("closeEnergyModal")
        self.record("workspace energy modal")

        self.current_page().call_method("addDesignToCart")
        self.wait_until(
            lambda: len(self.page_eval(self.current_page(), "function(){return wx.getStorageSync('diyDesignCart')||[];}") or []) > 0,
            "Design was not stored in cart",
            timeout=35,
        )
        self.record("workspace add to cart")

        cart = self.navigate_to(CART)
        cart.wait_for(".cart-page", max_timeout=15)
        self.wait_until(lambda: len(self.current_page().data.get("items") or []) > 0, "Cart did not load added design", timeout=18)
        cart_item = (self.current_page().data.get("items") or [{}])[0]
        self.assertTrue(cart_item.get("imageUrl") or cart_item.get("miniBeads"), "Cart thumbnail missing")
        self.assertNotIn("bead_", str(cart_item.get("recipeText") or ""), "Cart recipe exposes raw bead SKU text")
        self.screenshot("14_cart_with_design")
        self.record("cart display", detail=f"items={len(self.current_page().data.get('items') or [])}, image={bool(cart_item.get('imageUrl'))}")

        self.current_page().get_element(".cart-item", max_timeout=10).click()
        self.wait_path(WORKSPACE, timeout=20)
        self.wait_until(lambda: len(self.current_page().data.get("selected") or []) > 0, "Cart item did not reopen in workspace", timeout=18)
        self.screenshot("15_cart_reopens_workspace")
        self.record("cart item opens workspace", detail=f"count={len(self.current_page().data.get('selected') or [])}")

        self.navigate_to(CART)
        self.wait_until(lambda: len(self.current_page().data.get("items") or []) > 0, "Cart cleanup target missing", timeout=12)
        if not self.current_page().data.get("selectedKeys"):
            self.current_page().call_method("selectAll")
        self.current_page().call_method("removeSelectedItems")
        try:
            self.wait_until(lambda: len(self.current_page().data.get("items") or []) == 0, "Cart cleanup failed", timeout=20)
            self.record("cart cleanup")
        except AssertionError as error:
            self.screenshot("16_cart_cleanup_failed")
            self.record("cart cleanup", "FAIL", str(error))

        self.app.navigate_back()
        self.wait_path(WORKSPACE, timeout=12)
        self.current_page().call_method("goToCheckout")
        self.wait_path(CHECKOUT, timeout=35)
        checkout = self.current_page()
        checkout.wait_for(".checkout-page", max_timeout=15)
        self.wait_until(lambda: bool(self.current_page().data.get("design")), "Checkout design missing", timeout=15)
        checkout.call_method("submitOrder")
        self.wait_until(lambda: bool(self.current_page().data.get("addressError")), "Checkout did not validate missing address", timeout=10)
        self.screenshot("16_checkout_validation")
        self.record("checkout validation", detail=self.current_page().data.get("addressError", ""))

        self.app.navigate_to(f"{ORDER_LIST}?status=done")
        order_list = self.wait_path(ORDER_LIST, timeout=18)
        order_list.wait_for(".order-list-page", max_timeout=15)
        self.wait_until(lambda: not self.current_page().data.get("loading"), "Order list still loading", timeout=20)
        self.assertFalse(self.current_page().data.get("showListCount"), "Completed order tab should not show count")
        self.screenshot("17_order_done_tab")
        self.record(
            "completed order tab",
            detail=f"orders={len(self.current_page().data.get('filteredOrders') or [])}, showListCount={self.current_page().data.get('showListCount')}",
        )
