import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import homepageVideo from "../assets/video_homepage.mp4";
import CurtainFooter from "../components/CurtainFooter";
import SiteHeader from "../components/SiteHeader";
import "./Home.css";

gsap.registerPlugin(ScrollTrigger);

const philosophyCards = [
  {
    className: "card-clean",
    icon: "QR",
    title: "Check-in thông minh",
    text: "Xác thực hội viên bằng QR nhanh chóng, kiểm tra gói tập và chống quét lặp tự động."
  },
  {
    className: "card-transparent",
    icon: "↗",
    title: "Dữ liệu trực quan",
    text: "Theo dõi doanh thu, lượt check-in và hiệu suất lớp học trên dashboard theo thời gian thực."
  },
  {
    className: "card-potent",
    icon: "PT",
    title: "Lịch tập liền mạch",
    text: "Quản lý lớp nhóm, sức chứa, waitlist và lịch PT trong một quy trình thống nhất."
  },
  {
    className: "card-conscious",
    icon: "24",
    title: "Vận hành chủ động",
    text: "Nhắc gia hạn, thông báo lịch tập và lưu audit log giúp đội ngũ luôn kiểm soát hệ thống."
  }
];

const potencyProducts = [
  {
    name: "Gói theo tháng",
    price: "500.000đ",
    tag: "Linh hoạt",
    type: "Gói 30 ngày",
    headline: "Khởi đầu linh hoạt, đầy đủ quyền tập luyện.",
    description: "Không giới hạn check-in, đặt lớp nhóm và theo dõi lịch sử tập luyện.",
    image:
      "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=85"
  },
  {
    name: "Gói theo năm",
    price: "4.200.000đ",
    tag: "Giảm 30%",
    type: "Gói 12 tháng",
    headline: "Cam kết dài hạn, tiết kiệm 1.800.000đ.",
    description:
      "Toàn bộ quyền lợi gói tháng, ưu tiên booking và đánh giá thể trạng định kỳ.",
    image:
      "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?auto=format&fit=crop&w=1200&q=85"
  },
  {
    name: "Personal Training",
    price: "200.000đ",
    tag: "PT 1:1",
    type: "Tính theo buổi",
    headline: "Huấn luyện cá nhân theo đúng mục tiêu.",
    description:
      "Đánh giá kỹ thuật, xây dựng giáo án và theo sát tiến độ cùng huấn luyện viên.",
    image:
      "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=1200&q=85"
  }
];

export default function Home() {
  const transparencyRef = useRef(null);

  useEffect(() => {
    const lenis = new Lenis({
      smoothWheel: true,
      wheelMultiplier: 0.85
    });

    const updateLenis = (time) => {
      lenis.raf(time * 1000);
    };

    gsap.ticker.add(updateLenis);
    gsap.ticker.lagSmoothing(0);

    lenis.on("scroll", () => {
      ScrollTrigger.update();
      window.dispatchEvent(new Event("lenis-scroll"));
    });

    return () => {
      gsap.ticker.remove(updateLenis);
      lenis.destroy();
    };
  }, []);

  useEffect(() => {
    const revealTargets = [...document.querySelectorAll(".section-spacer, .products-side")];

    if (revealTargets.length === 0) {
      return undefined;
    }

    const triggers = revealTargets.map((target) =>
      ScrollTrigger.create({
        trigger: target,
        start: "top 78%",
        once: true,
        onEnter: () => {
          target.classList.add("is-revealed");
        }
      })
    );

    return () => {
      triggers.forEach((trigger) => trigger.kill());
      revealTargets.forEach((target) => target.classList.remove("is-revealed"));
    };
  }, []);

  useEffect(() => {
    const section = document.querySelector(".philosophy-section");
    const sticky = document.querySelector(".philosophy-sticky");
    const portrait = document.querySelector(".portrait-layer");
    const cards = [...document.querySelectorAll(".philosophy-section .floating-card")];
    const curvePaths = [...document.querySelectorAll(".philosophy-curve path")];

    if (!section || !sticky || !portrait || cards.length === 0) {
      return undefined;
    }

    const desktopQuery = window.matchMedia("(min-width: 1051px)");
    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    const lerp = (start, end, amount) => start + (end - start) * amount;

    const state = {
      target: 0,
      current: 0,
      raf: null
    };

    const syncPhilosophyEntrance = (progress) => {
      const eased = 1 - Math.pow(1 - progress, 3);

      sticky.style.setProperty("--philosophy-enter", eased.toFixed(4));
      sticky.style.setProperty("--philosophy-heading-y", `${lerp(44, 0, eased).toFixed(2)}px`);
      sticky.style.setProperty("--philosophy-script-y", `${lerp(68, 0, eased).toFixed(2)}px`);
      sticky.style.setProperty("--philosophy-portrait-y", `${lerp(76, 0, eased).toFixed(2)}px`);
      sticky.style.setProperty("--philosophy-portrait-scale", lerp(0.965, 1, eased).toFixed(4));
      sticky.style.setProperty("--philosophy-leaf-y", `${lerp(54, 0, eased).toFixed(2)}px`);
      sticky.style.setProperty("--curve-x", `${lerp(92, 0, eased).toFixed(2)}px`);
      sticky.style.setProperty("--curve-y", `${lerp(-28, 0, eased).toFixed(2)}px`);
      sticky.style.setProperty("--curve-progress", clamp((progress - 0.16) / 0.72, 0, 1).toFixed(4));
    };

    curvePaths.forEach((path) => {
      path.setAttribute("pathLength", "1");
    });

    const entranceTrigger = ScrollTrigger.create({
      trigger: section,
      start: "top 84%",
      end: "top 22%",
      scrub: true,
      onUpdate: (self) => syncPhilosophyEntrance(self.progress)
    });

    const getProgress = () => {
      if (!desktopQuery.matches) {
        return 1;
      }

      const rect = section.getBoundingClientRect();
      const start = window.innerHeight * 0.94;
      const distance = rect.height + window.innerHeight * 0.58;

      return clamp((start - rect.top) / distance, 0, 1);
    };

    const render = () => {
      state.current += (state.target - state.current) * 0.11;

      const progress = state.current;
      const imageY = lerp(46, -30, progress);
      const imageScale = lerp(0.985, 1.018, progress);

      portrait.style.transform = `translate(-50%, calc(-50% + ${imageY.toFixed(2)}px)) scale(${imageScale.toFixed(4)})`;

      cards.forEach((card, index) => {
        const localProgress = clamp((progress - index * 0.045) / 0.7, 0, 1);
        const cardY = lerp(330, -250 - index * 12, localProgress);
        const opacity = clamp((localProgress - 0.06) / 0.34, 0, 1);

        card.style.transform = `translate3d(0, ${cardY.toFixed(2)}px, 0)`;
        card.style.opacity = opacity.toFixed(3);
      });

      if (Math.abs(state.target - state.current) > 0.001) {
        state.raf = requestAnimationFrame(render);
        return;
      }

      state.current = state.target;
      state.raf = null;
    };

    const updateTarget = () => {
      state.target = getProgress();

      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    };

    const resetForViewport = () => {
      if (desktopQuery.matches) {
        updateTarget();
        syncPhilosophyEntrance(entranceTrigger.progress);
        return;
      }

      syncPhilosophyEntrance(1);
      portrait.style.transform = "";
      cards.forEach((card) => {
        card.style.transform = "";
        card.style.opacity = "";
      });
    };

    window.addEventListener("scroll", updateTarget, { passive: true });
    window.addEventListener("lenis-scroll", updateTarget);
    window.addEventListener("resize", resetForViewport);
    desktopQuery.addEventListener("change", resetForViewport);

    updateTarget();
    syncPhilosophyEntrance(entranceTrigger.progress);

    return () => {
      window.removeEventListener("scroll", updateTarget);
      window.removeEventListener("lenis-scroll", updateTarget);
      window.removeEventListener("resize", resetForViewport);
      desktopQuery.removeEventListener("change", resetForViewport);
      entranceTrigger.kill();

      if (state.raf) {
        cancelAnimationFrame(state.raf);
      }

      sticky.removeAttribute("style");
      portrait.style.transform = "";
      cards.forEach((card) => {
        card.style.transform = "";
        card.style.opacity = "";
      });
    };
  }, []);

  useEffect(() => {
    const section = document.querySelector(".potency-section");
    const productsSide = document.querySelector(".products-side");
    const railWindow = document.querySelector("#railWindow");
    const rail = document.querySelector("#productRail");
    const portraitImage = document.querySelector("#portraitImage");
    const cards = [...document.querySelectorAll(".potency-section .product-card")];
    const prevButton = document.querySelector("#prevButton");
    const nextButton = document.querySelector("#nextButton");
    const railProgress = document.querySelector("#railProgress");
    const dragCursor = document.querySelector("#dragCursor");
    const toast = document.querySelector("#toast");

    if (
      !section ||
      !productsSide ||
      !railWindow ||
      !rail ||
      !portraitImage ||
      !prevButton ||
      !nextButton ||
      !railProgress ||
      !dragCursor ||
      !toast
    ) {
      return undefined;
    }

    const drag = {
      pressed: false,
      pointerId: null,
      startX: 0,
      startOffset: 0,
      targetOffset: 0,
      currentOffset: 0,
      previousX: 0,
      previousTime: 0,
      velocity: 0,
      raf: null
    };

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    const lerp = (start, end, amount) => start + (end - start) * amount;

    const imageMotion = {
      target: 0,
      current: 0,
      raf: null
    };

    const getImageProgress = () => {
      const rect = section.getBoundingClientRect();
      const distance = window.innerHeight + rect.height;

      return clamp((window.innerHeight - rect.top) / distance, 0, 1);
    };

    const renderImageParallax = () => {
      imageMotion.current += (imageMotion.target - imageMotion.current) * 0.1;

      const imageY = lerp(54, -54, imageMotion.current);
      portraitImage.style.setProperty("--potency-image-y", `${imageY.toFixed(2)}px`);

      if (Math.abs(imageMotion.target - imageMotion.current) > 0.001) {
        imageMotion.raf = requestAnimationFrame(renderImageParallax);
        return;
      }

      imageMotion.current = imageMotion.target;
      imageMotion.raf = null;
    };

    const updateImageParallax = () => {
      imageMotion.target = getImageProgress();

      if (!imageMotion.raf) {
        imageMotion.raf = requestAnimationFrame(renderImageParallax);
      }
    };

    const getRailBounds = () => {
      const productSideWidth =
        window.innerWidth > 980 ? productsSide.getBoundingClientRect().width : window.innerWidth;
      const styles = window.getComputedStyle(productsSide);
      const sidePaddingRight = Number.parseFloat(styles.paddingRight) || 0;
      const padding = window.innerWidth < 560 ? 20 : 26;

      return {
        max: 0,
        min: Math.min(0, productSideWidth - rail.scrollWidth - padding - sidePaddingRight)
      };
    };

    const clampRailOffset = (value) => {
      const bounds = getRailBounds();
      return clamp(value, bounds.min, bounds.max);
    };

    const renderRail = () => {
      if (!drag.pressed) {
        drag.targetOffset += drag.velocity;
        drag.velocity *= 0.93;

        const bounds = getRailBounds();

        if (drag.targetOffset < bounds.min) {
          drag.targetOffset += (bounds.min - drag.targetOffset) * 0.13;
          drag.velocity *= 0.72;
        }

        if (drag.targetOffset > bounds.max) {
          drag.targetOffset += (bounds.max - drag.targetOffset) * 0.13;
          drag.velocity *= 0.72;
        }
      }

      drag.currentOffset +=
        (drag.targetOffset - drag.currentOffset) * (drag.pressed ? 0.28 : 0.11);

      rail.style.setProperty("--rail-x", `${drag.currentOffset.toFixed(2)}px`);

      const bounds = getRailBounds();
      const distance = Math.abs(bounds.min);
      const progress = distance ? clamp(Math.abs(drag.currentOffset) / distance, 0, 1) : 0;

      railProgress.style.setProperty("--drag-progress", progress.toFixed(4));

      const moving =
        drag.pressed ||
        Math.abs(drag.velocity) > 0.03 ||
        Math.abs(drag.targetOffset - drag.currentOffset) > 0.08;

      if (moving) {
        drag.raf = requestAnimationFrame(renderRail);
      } else {
        drag.targetOffset = clampRailOffset(drag.targetOffset);
        drag.currentOffset = drag.targetOffset;
        drag.raf = null;
      }
    };

    const ensureRailAnimation = () => {
      if (!drag.raf) {
        drag.raf = requestAnimationFrame(renderRail);
      }
    };

    const handlePointerDown = (event) => {
      if (event.target.closest("button")) {
        return;
      }

      drag.pressed = true;
      drag.pointerId = event.pointerId;
      drag.startX = event.clientX;
      drag.startOffset = drag.targetOffset;
      drag.previousX = event.clientX;
      drag.previousTime = performance.now();
      drag.velocity = 0;

      rail.classList.add("is-dragging");
      rail.setPointerCapture(event.pointerId);
      ensureRailAnimation();
    };

    const handlePointerMove = (event) => {
      dragCursor.style.transform = `translate3d(${event.clientX - 34}px, ${event.clientY - 34}px, 0)`;

      if (!drag.pressed || event.pointerId !== drag.pointerId) {
        return;
      }

      const now = performance.now();
      const deltaX = event.clientX - drag.startX;
      const frameDeltaX = event.clientX - drag.previousX;
      const frameTime = Math.max(now - drag.previousTime, 1);

      drag.targetOffset = drag.startOffset + deltaX * 0.9;
      drag.velocity = (frameDeltaX / frameTime) * 16;
      drag.previousX = event.clientX;
      drag.previousTime = now;

      ensureRailAnimation();
    };

    const endDrag = (event = {}) => {
      if (!drag.pressed) {
        return;
      }

      if (event.pointerId !== undefined && event.pointerId !== drag.pointerId) {
        return;
      }

      drag.pressed = false;
      drag.pointerId = null;
      rail.classList.remove("is-dragging");
      ensureRailAnimation();
    };

    const showDragCursor = () => dragCursor.classList.add("show");
    const hideDragCursor = () => {
      dragCursor.classList.remove("show");
      endDrag();
    };

    const goPrevious = () => {
      drag.targetOffset = clampRailOffset(drag.targetOffset + 320);
      drag.velocity = 0;
      ensureRailAnimation();
    };

    const goNext = () => {
      drag.targetOffset = clampRailOffset(drag.targetOffset - 320);
      drag.velocity = 0;
      ensureRailAnimation();
    };

    const cardHandlers = cards.map((card) => {
      const handleCardMove = (event) => {
        if (drag.pressed || window.matchMedia("(hover: none)").matches) {
          return;
        }

        const rect = card.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width;
        const y = (event.clientY - rect.top) / rect.height;

        card.style.setProperty("--ry", `${((x - 0.5) * 6).toFixed(2)}deg`);
        card.style.setProperty("--rx", `${((0.5 - y) * 5).toFixed(2)}deg`);
      };

      const resetCardTilt = () => {
        card.style.setProperty("--rx", "0deg");
        card.style.setProperty("--ry", "0deg");
      };

      const toggleTouchPanel = (event) => {
        if (window.matchMedia("(hover: none)").matches && !event.target.closest("button")) {
          card.classList.toggle("is-open");
        }
      };

      card.addEventListener("pointermove", handleCardMove);
      card.addEventListener("pointerleave", resetCardTilt);
      card.addEventListener("click", toggleTouchPanel);

      return () => {
        card.removeEventListener("pointermove", handleCardMove);
        card.removeEventListener("pointerleave", resetCardTilt);
        card.removeEventListener("click", toggleTouchPanel);
      };
    });

    let toastTimer;
    const addButtons = [...document.querySelectorAll(".potency-section .add-button")];
    const addButtonHandlers = addButtons.map((button) => {
      const handleAdd = (event) => {
        event.stopPropagation();

        button.textContent = "Added ✓";
        button.disabled = true;
        toast.classList.add("show");
        window.clearTimeout(toastTimer);

        toastTimer = window.setTimeout(() => {
          toast.classList.remove("show");
        }, 1500);

        window.setTimeout(() => {
          button.textContent = "Chọn gói";
          button.disabled = false;
        }, 1400);
      };

      button.addEventListener("click", handleAdd);

      return () => button.removeEventListener("click", handleAdd);
    });

    const getRailEnterOffset = () => clamp(window.innerWidth * -0.16, -220, -96);

    const syncRailEntrance = (progress) => {
      railWindow.style.setProperty(
        "--rail-enter-x",
        `${lerp(getRailEnterOffset(), 0, progress).toFixed(2)}px`
      );
      railWindow.style.opacity = clamp(progress * 1.2, 0, 1).toFixed(3);
    };

    const handleResize = () => {
      updateImageParallax();
      drag.targetOffset = clampRailOffset(drag.targetOffset);
      syncRailEntrance(railEnterTrigger.progress);
      ensureRailAnimation();
    };

    rail.addEventListener("pointerdown", handlePointerDown);
    rail.addEventListener("pointermove", handlePointerMove);
    rail.addEventListener("pointerup", endDrag);
    rail.addEventListener("pointercancel", endDrag);
    rail.addEventListener("lostpointercapture", endDrag);
    rail.addEventListener("mouseenter", showDragCursor);
    rail.addEventListener("mouseleave", hideDragCursor);
    prevButton.addEventListener("click", goPrevious);
    nextButton.addEventListener("click", goNext);
    window.addEventListener("scroll", updateImageParallax, { passive: true });
    window.addEventListener("lenis-scroll", updateImageParallax);
    window.addEventListener("resize", handleResize);

    const railEnterTrigger = ScrollTrigger.create({
      trigger: section,
      start: "top 88%",
      end: "top 20%",
      scrub: true,
      onUpdate: (self) => syncRailEntrance(self.progress)
    });

    syncRailEntrance(railEnterTrigger.progress);
    updateImageParallax();
    ensureRailAnimation();

    return () => {
      rail.removeEventListener("pointerdown", handlePointerDown);
      rail.removeEventListener("pointermove", handlePointerMove);
      rail.removeEventListener("pointerup", endDrag);
      rail.removeEventListener("pointercancel", endDrag);
      rail.removeEventListener("lostpointercapture", endDrag);
      rail.removeEventListener("mouseenter", showDragCursor);
      rail.removeEventListener("mouseleave", hideDragCursor);
      prevButton.removeEventListener("click", goPrevious);
      nextButton.removeEventListener("click", goNext);
      window.removeEventListener("scroll", updateImageParallax);
      window.removeEventListener("lenis-scroll", updateImageParallax);
      window.removeEventListener("resize", handleResize);
      cardHandlers.forEach((cleanup) => cleanup());
      addButtonHandlers.forEach((cleanup) => cleanup());
      railEnterTrigger.kill();
      window.clearTimeout(toastTimer);

      if (imageMotion.raf) {
        cancelAnimationFrame(imageMotion.raf);
      }

      if (drag.raf) {
        cancelAnimationFrame(drag.raf);
      }

      portraitImage.style.removeProperty("--potency-image-y");
    };
  }, []);

  useEffect(() => {
    const story = transparencyRef.current;
    const stage = story?.querySelector("#transparencyStage");
    const headlineOne = story?.querySelector("#headlineOne");
    const headlineTwo = story?.querySelector("#headlineTwo");
    const fineCopy = story?.querySelector("#fineCopy");
    const liquidArt = story?.querySelector("#liquidArt");
    const cards = story ? [...story.querySelectorAll("[data-parallax-card]")] : [];
    const philosophyLink = story?.querySelector("#philosophyLink");
    const transparencyProgress = story?.querySelector("#transparencyProgress");

    if (
      !story ||
      !stage ||
      !headlineOne ||
      !headlineTwo ||
      !fineCopy ||
      !liquidArt ||
      !philosophyLink ||
      !transparencyProgress ||
      cards.length < 2
    ) {
      return undefined;
    }

    const state = {
      target: 0,
      current: 0,
      mouseX: 0,
      mouseY: 0,
      smoothMouseX: 0,
      smoothMouseY: 0,
      raf: null
    };

    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    const lerp = (start, end, amount) => start + (end - start) * amount;

    const getProgress = () => {
      const rect = story.getBoundingClientRect();
      const distance = Math.max(story.offsetHeight - window.innerHeight, 1);
      return clamp(-rect.top / distance, 0, 1);
    };

    const render = () => {
      state.current += (state.target - state.current) * 0.07;
      state.smoothMouseX += (state.mouseX - state.smoothMouseX) * 0.075;
      state.smoothMouseY += (state.mouseY - state.smoothMouseY) * 0.075;

      const progress = state.current;
      const mouseX = state.smoothMouseX;
      const mouseY = state.smoothMouseY;
      const textOneY = lerp(112, 0, clamp(progress / 0.22, 0, 1));
      const textTwoY = lerp(112, 0, clamp((progress - 0.15) / 0.24, 0, 1));
      const copyProgress = clamp((progress - 0.12) / 0.22, 0, 1);
      const cardOneProgress = clamp((progress - 0.23) / 0.26, 0, 1);
      const cardTwoProgress = clamp((progress - 0.37) / 0.26, 0, 1);
      const buttonProgress = clamp((progress - 0.48) / 0.22, 0, 1);

      headlineOne.style.setProperty("--text-y", `${textOneY.toFixed(2)}%`);
      headlineTwo.style.setProperty("--text-y", `${textTwoY.toFixed(2)}%`);
      fineCopy.style.setProperty("--copy-y", `${lerp(42, 0, copyProgress).toFixed(2)}px`);
      fineCopy.style.setProperty("--copy-opacity", copyProgress.toFixed(3));

      liquidArt.style.setProperty("--art-x", `${(mouseX * 15 + lerp(-20, 25, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--art-y", `${(mouseY * 12 + lerp(30, -45, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--art-r", `${lerp(-1.4, 1.4, progress).toFixed(3)}deg`);
      liquidArt.style.setProperty("--art-scale", lerp(1.04, 1, progress).toFixed(4));
      liquidArt.style.setProperty("--stroke-a-x", `${(mouseX * -18 + lerp(-30, 32, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--stroke-a-y", `${(mouseY * -10 + lerp(36, -46, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--stroke-b-x", `${(mouseX * 23 + lerp(42, -24, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--stroke-b-y", `${(mouseY * 14 + lerp(-15, 26, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--stroke-c-x", `${(mouseX * -12 + lerp(20, -18, progress)).toFixed(2)}px`);
      liquidArt.style.setProperty("--stroke-c-y", `${(mouseY * 18 + lerp(-26, 22, progress)).toFixed(2)}px`);

      cards[0].style.setProperty("--card-x", `${lerp(-210, 0, cardOneProgress).toFixed(2)}px`);
      cards[0].style.setProperty("--card-y", `${lerp(90, -18, cardOneProgress).toFixed(2)}px`);
      cards[0].style.setProperty("--card-r", `${lerp(-7, -1.4, cardOneProgress).toFixed(2)}deg`);
      cards[0].style.setProperty("--card-opacity", cardOneProgress.toFixed(3));

      cards[1].style.setProperty("--card-x", `${lerp(220, 0, cardTwoProgress).toFixed(2)}px`);
      cards[1].style.setProperty("--card-y", `${lerp(110, -8, cardTwoProgress).toFixed(2)}px`);
      cards[1].style.setProperty("--card-r", `${lerp(7, 1.3, cardTwoProgress).toFixed(2)}deg`);
      cards[1].style.setProperty("--card-opacity", cardTwoProgress.toFixed(3));

      philosophyLink.style.setProperty("--button-scale", lerp(0.72, 1, buttonProgress).toFixed(4));
      philosophyLink.style.setProperty("--button-opacity", buttonProgress.toFixed(3));
      transparencyProgress.style.setProperty("--section-progress", progress.toFixed(4));

      const stillMoving =
        Math.abs(state.target - state.current) > 0.0005 ||
        Math.abs(state.mouseX - state.smoothMouseX) > 0.001 ||
        Math.abs(state.mouseY - state.smoothMouseY) > 0.001;

      if (stillMoving) {
        state.raf = requestAnimationFrame(render);
      } else {
        state.current = state.target;
        state.raf = null;
      }
    };

    const updateTarget = () => {
      state.target = getProgress();

      if (Math.abs(state.target - state.current) > 0.35) {
        state.current += (state.target - state.current) * 0.35;
      }

      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    };

    const handleStagePointerMove = (event) => {
      const rect = stage.getBoundingClientRect();
      state.mouseX = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
      state.mouseY = ((event.clientY - rect.top) / rect.height - 0.5) * 2;

      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    };

    const resetStageMouse = () => {
      state.mouseX = 0;
      state.mouseY = 0;

      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    };

    const cardCleanups = cards.map((card) => {
      const handleMove = (event) => {
        const rect = card.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;

        card.style.setProperty("--mx", `${(x * 12).toFixed(2)}px`);
        card.style.setProperty("--my", `${(y * 12).toFixed(2)}px`);
      };

      const resetMove = () => {
        card.style.setProperty("--mx", "0px");
        card.style.setProperty("--my", "0px");
      };

      card.addEventListener("pointermove", handleMove);
      card.addEventListener("pointerleave", resetMove);

      return () => {
        card.removeEventListener("pointermove", handleMove);
        card.removeEventListener("pointerleave", resetMove);
      };
    });

    const handleButtonMove = (event) => {
      const rect = philosophyLink.getBoundingClientRect();
      const x = event.clientX - (rect.left + rect.width / 2);
      const y = event.clientY - (rect.top + rect.height / 2);

      philosophyLink.style.setProperty("--bx", `${(x * 0.24).toFixed(2)}px`);
      philosophyLink.style.setProperty("--by", `${(y * 0.24).toFixed(2)}px`);
    };

    const resetButton = () => {
      philosophyLink.style.setProperty("--bx", "0px");
      philosophyLink.style.setProperty("--by", "0px");
    };

    const syncProgress = (progress) => {
      state.target = clamp(progress, 0, 1);

      if (Math.abs(state.target - state.current) > 0.35) {
        state.current += (state.target - state.current) * 0.35;
      }

      if (!state.raf) {
        state.raf = requestAnimationFrame(render);
      }
    };

    const transparencyTrigger = ScrollTrigger.create({
      trigger: story,
      start: "top top",
      end: "bottom bottom",
      scrub: 1.15,
      invalidateOnRefresh: true,
      onUpdate: (self) => syncProgress(self.progress),
      onRefresh: (self) => syncProgress(self.progress)
    });

    const handleResize = () => {
      ScrollTrigger.refresh();
      syncProgress(transparencyTrigger.progress);
    };

    const refreshTimer = window.setTimeout(() => {
      ScrollTrigger.refresh();
      syncProgress(transparencyTrigger.progress);
    }, 250);

    let progressLoop = null;
    const trackProgress = () => {
      updateTarget();
      progressLoop = requestAnimationFrame(trackProgress);
    };

    stage.addEventListener("pointermove", handleStagePointerMove);
    stage.addEventListener("pointerleave", resetStageMouse);
    philosophyLink.addEventListener("pointermove", handleButtonMove);
    philosophyLink.addEventListener("pointerleave", resetButton);
    window.addEventListener("resize", handleResize);

    trackProgress();
    syncProgress(transparencyTrigger.progress || getProgress());

    return () => {
      window.clearTimeout(refreshTimer);
      stage.removeEventListener("pointermove", handleStagePointerMove);
      stage.removeEventListener("pointerleave", resetStageMouse);
      philosophyLink.removeEventListener("pointermove", handleButtonMove);
      philosophyLink.removeEventListener("pointerleave", resetButton);
      window.removeEventListener("resize", handleResize);
      transparencyTrigger.kill();
      cardCleanups.forEach((cleanup) => cleanup());

      if (progressLoop) {
        cancelAnimationFrame(progressLoop);
      }

      if (state.raf) {
        cancelAnimationFrame(state.raf);
      }
    };
  }, []);

  return (
    <main>
      <SiteHeader autoHide />

      <section className="hero" id="home">
        <div className="video-frame" aria-hidden="true">
          <video autoPlay muted loop playsInline preload="auto">
            <source src={homepageVideo} type="video/mp4" />
          </video>
        </div>

        <div className="hero-content">
          <p className="eyebrow">Train hard. Live strong.</p>

          <h1 className="hero-title">
            <span>
              <em>Build</em> your
            </span>
            <span className="line-two">
              strongest <em>self</em>
            </span>
          </h1>

        </div>

        <aside className="hero-side-panel">
          <p className="hero-panel-label">All-in-one fitness platform</p>
          <p className="hero-copy">
            Một nền tảng quản lý phòng gym hiện đại cho hội viên, huấn luyện viên và đội ngũ
            vận hành cùng tiến về phía trước.
          </p>

          <div className="hero-meta" aria-label="Điểm nổi bật">
            <span><strong>24/7</strong> QR check-in</span>
            <span><strong>01</strong> hệ thống vận hành</span>
          </div>
        </aside>

        <a className="hero-cta" href="/plans">
          <span className="label">Khám phá gói tập</span>
          <span className="arrow" aria-hidden="true">
            →
          </span>
        </a>

        <span className="scroll-line" aria-hidden="true" />
      </section>

      <section className="section-spacer philosophy-intro" id="philosophy" aria-label="Nền tảng quản lý phòng gym">
        <div className="section-spacer-line" />
        <span className="section-spacer-arrow" aria-hidden="true">
          ↴
        </span>
      </section>

      <section className="philosophy-section" id="philosophySection">
        <div className="philosophy-sticky">
          <div className="philosophy-heading">
            <h2>
              SMART, CONNECTED,
              <br />
              FITNESS
            </h2>
            <p>
              Từ check-in đến thanh toán, mọi hoạt động được kết nối trong một trải nghiệm
              nhanh, rõ ràng và dễ kiểm soát.
            </p>
          </div>

          <div className="script-title">stronger.</div>

          <svg className="philosophy-curve" viewBox="0 0 700 600" aria-hidden="true">
            <path
              d="M40 30 C 410 -80, 760 180, 550 510"
              fill="none"
              pathLength="1"
              stroke="currentColor"
            />
            <path
              d="M550 510 L535 492 M550 510 L558 487"
              fill="none"
              pathLength="1"
              stroke="currentColor"
            />
          </svg>

          <div className="portrait-layer">
            <div className="portrait-shape">
              <img
                src="https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1500&q=85"
                alt="Không gian tập luyện hiện đại"
              />
            </div>
          </div>

          <span className="floating-leaf" aria-hidden="true">
            ◜
          </span>

          {philosophyCards.map((card) => (
            <article className={`floating-card ${card.className}`} key={card.title}>
              <div className="card-icon">
                <span>{card.icon}</span>
              </div>
              <h3>{card.title}</h3>
              <p>{card.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section-spacer" id="products" aria-label="Khám phá gói hội viên">
        <div className="section-spacer-line" />
        <div className="section-spacer-title">
          <span>Chọn gói</span>
          <em>vượt giới hạn</em>
        </div>
        <span className="section-spacer-arrow" aria-hidden="true">
          ↴
        </span>
      </section>

      <section className="potency-section" id="potencySection">
        <section className="products-side">
          <header className="section-heading" id="sectionHeading">
            <p className="eyebrow">Membership plans</p>

            <h2>
              Chọn gói
              <em>đúng mục tiêu</em>
            </h2>
          </header>

          <div className="rail-window" id="railWindow">
            <div className="product-rail" id="productRail">
              {potencyProducts.map((product) => (
                <article className="product-card" tabIndex="0" key={product.name}>
                  <div className="card-top">
                    <span className="pill">{product.tag}</span>
                    <span className="bag">
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M6.8 8.5h10.4l.8 11H6l.8-11Z" />
                        <path d="M9 9V6.8a3 3 0 0 1 6 0V9" />
                      </svg>
                    </span>
                  </div>

                  <div className="media">
                    <img src={product.image} alt={product.name} draggable="false" />
                  </div>

                  <div className="product-info">
                    <span className="name">{product.name}</span>
                    <span className="price">{product.price}</span>
                  </div>

                  <div className="hover-panel">
                    <small>{product.type}</small>
                    <h3>{product.headline}</h3>
                    <p>{product.description}</p>

                    <div className="hover-actions">
                      <button className="add-button" type="button">
                        Chọn gói
                      </button>
                      <button className="details-button" type="button">
                        →
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="controls">
            <button id="prevButton" type="button" aria-label="Sản phẩm trước">
              ←
            </button>
            <button id="nextButton" type="button" aria-label="Sản phẩm tiếp theo">
              →
            </button>

            <div className="rail-progress">
              <span id="railProgress" />
            </div>
          </div>
        </section>

        <aside className="image-side">
          <div className="image-frame" id="imageFrame">
            <img
              id="portraitImage"
              src="https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=1600&q=85"
              alt="Hội viên tập luyện cùng huấn luyện viên"
              draggable="false"
            />
          </div>

          <span className="image-label">IRONIX PERFORMANCE</span>

          <div className="image-copy" id="imageCopy">
            <h3>Kỷ luật hôm nay. Sức mạnh ngày mai.</h3>
            <span>Kéo để khám phá</span>
          </div>

          <div className="section-progress">
            <span id="sectionProgress" />
          </div>
        </aside>

        <div className="drag-cursor" id="dragCursor">
          Kéo
        </div>
        <div className="toast" id="toast">
          Đã chọn gói ✓
        </div>
      </section>

      <section className="section-spacer transparency-intro" id="collections" aria-label="Quản lý minh bạch">
        <div className="section-spacer-line" />
        <div className="section-spacer-title">
          <span>Dữ liệu</span>
          <em>minh bạch</em>
        </div>
        <span className="section-spacer-arrow" aria-hidden="true">
          ↴
        </span>
      </section>

      <section className="transparency-story" id="transparencyStory" ref={transparencyRef}>
        <div className="transparency-stage" id="transparencyStage">
          <div className="headline" aria-hidden="true">
            <div className="headline-line headline-line--one">
              <span id="headlineOne">Control Every Rep.</span>
            </div>

            <div className="headline-line headline-line--two">
              <span id="headlineTwo">Miss Nothing.</span>
            </div>
          </div>

          <p className="fine-copy" id="fineCopy">
            Hội viên, gói tập, check-in và doanh thu được cập nhật rõ ràng để mọi quyết định
            vận hành đều dựa trên dữ liệu đáng tin cậy.
          </p>

          <svg
            className="liquid-art"
            id="liquidArt"
            viewBox="0 0 1600 900"
            preserveAspectRatio="xMidYMid slice"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="paintA" x1="0" x2="1">
                <stop offset="0" stopColor="#d6ff3f" />
                <stop offset=".5" stopColor="#91b51d" />
                <stop offset="1" stopColor="#27320b" />
              </linearGradient>

              <linearGradient id="paintB" x1="0" x2="1">
                <stop offset="0" stopColor="#f5f5f5" />
                <stop offset=".52" stopColor="#a7c92f" />
                <stop offset="1" stopColor="#465616" />
              </linearGradient>

              <filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="24"
                  stdDeviation="26"
                  floodColor="#000000"
                  floodOpacity=".16"
                />
              </filter>
            </defs>

            <g className="stroke-a" filter="url(#softShadow)">
              <path
                d="M-130 690 C 130 590, 315 590, 485 686 C 642 775, 805 830, 1060 756 C 1275 694, 1445 557, 1710 520 L 1700 855 C 1430 880, 1240 925, 1010 930 C 790 935, 580 914, 376 870 C 158 823, -40 804, -130 825 Z"
                fill="url(#paintA)"
              />
            </g>

            <g className="stroke-b" filter="url(#softShadow)">
              <path
                d="M110 520 C 225 384, 420 333, 638 360 C 818 381, 935 483, 1080 451 C 1195 426, 1284 340, 1437 311 C 1513 297, 1582 302, 1660 326 L 1602 530 C 1472 520, 1393 544, 1304 602 C 1149 702, 1008 704, 848 630 C 668 547, 524 518, 381 568 C 270 607, 191 642, 110 651 Z"
                fill="url(#paintB)"
                opacity=".96"
              />
            </g>

            <g className="stroke-c">
              <path
                d="M965 116 C 1106 34, 1296 62, 1405 170 C 1493 257, 1522 374, 1467 482 C 1408 599, 1281 665, 1164 627 C 1055 591, 993 497, 1003 400 C 1011 318, 1076 270, 1146 243 C 1208 219, 1220 163, 1160 130 C 1110 102, 1037 101, 965 116 Z"
                fill="#d6ff3f"
                opacity=".75"
              />
            </g>
          </svg>

          <article className="fact-card fact-card--one" data-parallax-card>
            <div className="fact-index">
              <span>01</span>
              <span>Live operations</span>
            </div>

            <div className="fact-icon">
              <svg viewBox="0 0 48 48" aria-hidden="true">
                <circle cx="20" cy="20" r="11" />
                <path d="M28 28l10 10" />
                <path d="M16 20h8" />
                <path d="M20 16v8" />
              </svg>
            </div>

            <h3>Dashboard vận hành tập trung</h3>

            <p>
              Nắm số hội viên active, lượt check-in, doanh thu và tình trạng lớp học trên một
              màn hình duy nhất.
            </p>
          </article>

          <article className="fact-card fact-card--two" data-parallax-card>
            <div className="fact-index">
              <span>02</span>
              <span>Secure by design</span>
            </div>

            <div className="fact-icon">
              <svg viewBox="0 0 48 48" aria-hidden="true">
                <path d="M17 7h14" />
                <path d="M20 7v11L10 36a4 4 0 0 0 3.5 6h21a4 4 0 0 0 3.5-6L28 18V7" />
                <path d="M15 31h18" />
                <circle cx="23" cy="26" r="2" />
                <circle cx="29" cy="34" r="1.5" />
              </svg>
            </div>

            <h3>Phân quyền và truy vết rõ ràng</h3>

            <p>
              RBAC theo vai trò, audit log và lịch sử trạng thái giúp mọi thao tác nhạy cảm đều
              được kiểm soát.
            </p>
          </article>

          <a className="philosophy-link" id="philosophyLink" href="#home">
            Xem
            <br />
            tính năng
          </a>

          <div className="scroll-indicator" aria-hidden="true">
            <span id="transparencyProgress" />
          </div>
        </div>
      </section>

      <section className="clean-journal-section" id="cleanJournal" aria-labelledby="cleanJournalTitle">
        <div className="clean-journal-sticky">
          <div className="clean-journal-layout">
            <div className="clean-journal-featured-wrap">
              <article className="clean-journal-featured">
                <div className="clean-journal-media">
                  <span className="clean-journal-badge">Nổi bật</span>
                  <svg
                    className="clean-journal-art"
                    viewBox="0 0 1200 900"
                    role="img"
                    aria-label="Minh họa bài viết về tập luyện"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <defs>
                      <linearGradient id="cleanJournalBgOne" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0" stopColor="#f3ead9" />
                        <stop offset="1" stopColor="#e4d4bc" />
                      </linearGradient>
                      <linearGradient id="cleanJournalBristle" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0" stopColor="#f0c69f" />
                        <stop offset=".55" stopColor="#b56f44" />
                        <stop offset="1" stopColor="#744229" />
                      </linearGradient>
                      <linearGradient id="cleanJournalGlass" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0" stopColor="#8c4d33" />
                        <stop offset=".5" stopColor="#d89d72" />
                        <stop offset="1" stopColor="#6c3527" />
                      </linearGradient>
                      <filter id="cleanJournalShadowOne" x="-40%" y="-40%" width="180%" height="180%">
                        <feDropShadow
                          dx="26"
                          dy="32"
                          stdDeviation="18"
                          floodColor="#3c2618"
                          floodOpacity=".35"
                        />
                      </filter>
                    </defs>
                    <rect width="1200" height="900" fill="url(#cleanJournalBgOne)" />
                    <g opacity=".72" stroke="#a18b6f" strokeWidth="2">
                      <path d="M360 110C560 50 740 55 970 120" />
                      <path d="M350 125C560 70 760 75 980 145" />
                      <path d="M345 140C565 88 770 92 995 168" />
                      <path d="M340 155C565 108 780 110 1000 190" />
                    </g>
                    <path
                      d="M520 235C745 160 930 175 1035 320C935 450 735 470 535 386Z"
                      fill="#aa6d53"
                      opacity=".88"
                    />
                    <path
                      d="M315 570C490 480 710 500 838 616C660 720 460 720 292 640Z"
                      fill="#cf8a63"
                      opacity=".82"
                    />
                    <g filter="url(#cleanJournalShadowOne)" transform="rotate(-22 430 300)">
                      <rect x="382" y="252" width="90" height="330" rx="15" fill="#eee8de" />
                      <rect x="394" y="330" width="66" height="182" rx="8" fill="#f7f3ed" />
                      <ellipse cx="427" cy="228" rx="105" ry="132" fill="url(#cleanJournalBristle)" />
                      <path
                        d="M335 222C365 84 495 80 528 218C475 177 389 175 335 222Z"
                        fill="#f0d0ad"
                        opacity=".55"
                      />
                    </g>
                    <g filter="url(#cleanJournalShadowOne)">
                      <rect x="548" y="490" width="180" height="255" rx="24" fill="#241a18" />
                      <rect x="564" y="505" width="148" height="215" rx="19" fill="url(#cleanJournalGlass)" />
                      <rect x="574" y="294" width="130" height="215" rx="7" fill="#111116" />
                      <rect x="585" y="309" width="108" height="181" rx="5" fill="#191821" />
                      <rect x="589" y="535" width="98" height="145" rx="10" fill="#cf936b" />
                    </g>
                  </svg>
                </div>

                <div className="clean-journal-featured-body">
                  <h3 className="clean-journal-featured-title">
                    Xây dựng lịch tập bền vững cho người mới bắt đầu
                  </h3>
                  <p className="clean-journal-featured-desc">
                    Cách kết hợp sức mạnh, cardio và phục hồi để duy trì tiến bộ mà không quá tải.
                  </p>
                  <footer className="clean-journal-footer">
                    <time className="clean-journal-date" dateTime="2026-07-08">
                      08 tháng 7, 2026
                    </time>
                    <a className="clean-journal-link" href="#cleanJournalArticleOne">
                      Đọc bài
                    </a>
                  </footer>
                </div>
              </article>
            </div>

            <header className="clean-journal-heading">
              <h2 className="clean-journal-title" id="cleanJournalTitle">
                <span className="clean-journal-script">ironix</span>
                <span className="clean-journal-bold">JOURNAL</span>
              </h2>
              <p>Kiến thức về tập luyện, dinh dưỡng, phục hồi và vận hành phòng gym hiệu quả.</p>
            </header>

            <div className="clean-journal-cards-wrap">
              <div className="clean-journal-cards">
                <article className="clean-journal-card" id="cleanJournalArticleOne">
                  <div className="clean-journal-media">
                    <svg
                      className="clean-journal-art"
                      viewBox="0 0 900 650"
                      role="img"
                      aria-label="Minh họa bài viết về phục hồi sau tập"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <defs>
                        <linearGradient id="cleanJournalBgTwo" x1="0" y1="0" x2="1" y2="1">
                          <stop offset="0" stopColor="#e6b997" />
                          <stop offset="1" stopColor="#d6a17e" />
                        </linearGradient>
                        <filter id="cleanJournalShadowTwo" x="-50%" y="-50%" width="200%" height="200%">
                          <feDropShadow
                            dx="15"
                            dy="18"
                            stdDeviation="14"
                            floodColor="#412519"
                            floodOpacity=".28"
                          />
                        </filter>
                      </defs>
                      <rect width="900" height="650" fill="url(#cleanJournalBgTwo)" />
                      <path d="M385 650C346 584 350 525 405 486C449 456 490 477 511 525L568 650Z" fill="#9c563f" />
                      <path d="M472 650C434 586 445 522 505 495C548 476 582 507 600 552L630 650Z" fill="#b96f53" />
                      <g filter="url(#cleanJournalShadowTwo)">
                        <rect x="390" y="365" width="175" height="300" rx="28" fill="#121212" />
                        <rect x="412" y="383" width="131" height="248" rx="16" fill="#1e1e1f" />
                        <rect x="416" y="295" width="123" height="86" rx="11" fill="#0d0d0e" />
                        <g stroke="#2f2f30" strokeWidth="8">
                          <line x1="425" y1="312" x2="531" y2="312" />
                          <line x1="425" y1="332" x2="531" y2="332" />
                          <line x1="425" y1="352" x2="531" y2="352" />
                        </g>
                      </g>
                      <path
                        d="M475 92C475 92 420 158 420 208C420 248 444 274 475 274C506 274 530 248 530 208C530 158 475 92 475 92Z"
                        fill="#d89266"
                        filter="url(#cleanJournalShadowTwo)"
                      />
                      <ellipse cx="457" cy="178" rx="13" ry="34" fill="#f0b78f" opacity=".55" transform="rotate(18 457 178)" />
                    </svg>
                  </div>
                  <div className="clean-journal-card-body">
                    <h3 className="clean-journal-card-title">Phục hồi đúng cách sau một buổi tập nặng</h3>
                    <footer className="clean-journal-footer">
                      <time className="clean-journal-date" dateTime="2026-06-24">
                        24 tháng 6, 2026
                      </time>
                      <a className="clean-journal-link" href="#cleanJournal">
                        Đọc bài
                      </a>
                    </footer>
                  </div>
                </article>

                <article className="clean-journal-card">
                  <div className="clean-journal-media">
                    <svg
                      className="clean-journal-art"
                      viewBox="0 0 900 650"
                      role="img"
                      aria-label="Minh họa bài viết về dinh dưỡng thể thao"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <defs>
                        <linearGradient id="cleanJournalSkinThree" x1="0" y1="0" x2="1" y2="1">
                          <stop offset="0" stopColor="#b97854" />
                          <stop offset="1" stopColor="#6e3d2b" />
                        </linearGradient>
                        <linearGradient id="cleanJournalLeafThree" x1="0" y1="0" x2="1" y2="1">
                          <stop offset="0" stopColor="#3f6e3c" />
                          <stop offset="1" stopColor="#163d23" />
                        </linearGradient>
                      </defs>
                      <rect width="900" height="650" fill="#c8b28b" />
                      <ellipse cx="650" cy="315" rx="330" ry="390" fill="url(#cleanJournalSkinThree)" />
                      <path d="M450 40C570 15 770 30 895 145L900 400C805 322 690 300 520 330C445 269 421 159 450 40Z" fill="#e7dfcd" />
                      <path d="M494 102C603 63 731 83 818 166C745 142 649 155 548 207C508 183 487 145 494 102Z" fill="#f1ecdf" opacity=".76" />
                      <path d="M626 275C682 250 738 256 782 289C735 307 682 311 630 300Z" fill="#2d1712" />
                      <path d="M650 286C685 271 724 273 754 291C717 302 686 304 653 298Z" fill="#f4eee5" />
                      <ellipse cx="704" cy="291" rx="16" ry="12" fill="#1f1714" />
                      <path d="M561 467C650 426 746 447 810 517C742 566 647 568 572 520Z" fill="#7a3028" />
                      <path d="M590 486C660 467 729 479 778 516C720 530 656 529 603 514Z" fill="#b75a4d" />
                      <g opacity=".98">
                        <path d="M-20 80C160 35 300 102 450 270C267 293 130 236 -20 80Z" fill="url(#cleanJournalLeafThree)" />
                        <path d="M-30 510C142 355 297 330 484 388C331 509 180 565 -30 510Z" fill="#285431" />
                        <path d="M93 -20C238 40 322 146 351 312C222 246 133 141 93 -20Z" fill="#4e7c45" />
                        <g stroke="#8eab73" strokeWidth="7" opacity=".72">
                          <path d="M10 96C145 144 277 199 420 264" />
                          <path d="M2 500C157 438 292 403 448 395" />
                        </g>
                      </g>
                    </svg>
                  </div>
                  <div className="clean-journal-card-body">
                    <h3 className="clean-journal-card-title">Dinh dưỡng đơn giản để tập khỏe mỗi ngày</h3>
                    <footer className="clean-journal-footer">
                      <time className="clean-journal-date" dateTime="2026-06-12">
                        12 tháng 6, 2026
                      </time>
                      <a className="clean-journal-link" href="#cleanJournal">
                        Đọc bài
                      </a>
                    </footer>
                  </div>
                </article>
              </div>
            </div>

            <div className="clean-journal-nav-wrap">
              <a className="clean-journal-nav" href="#home" aria-label="Về đầu trang">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M6 18L18 6M18 6H8M18 6V16"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </section>

      <CurtainFooter
        brand="IRONIX Fitness"
        wordmark="IRONIX."
        description="Nền tảng quản lý phòng gym kết nối hội viên, huấn luyện viên và đội ngũ vận hành."
        image="https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1800&q=85"
        imageAlt="Không gian phòng gym IRONIX"
        columns={[
          {
            title: "Khám phá",
            links: [
              { label: "Home", href: "/" },
              { label: "Sản phẩm", href: "/products" },
              { label: "Gói tập", href: "/plans" },
              { label: "Tính năng", href: "#philosophy" },
              { label: "Kiến thức", href: "#cleanJournal" }
            ]
          },
          {
            title: "Hỗ trợ",
            links: [
              { label: "Liên hệ", href: "#home" },
              { label: "Điều khoản", href: "#home" },
              { label: "Bảo mật", href: "#home" }
            ]
          },
          {
            title: "Tài khoản",
            links: [
              { label: "Đăng nhập", href: "/login" },
              { label: "Đăng ký", href: "/signup" },
              { label: "Dashboard", href: "/dashboard" }
            ]
          }
        ]}
      />
    </main>
  );
}

