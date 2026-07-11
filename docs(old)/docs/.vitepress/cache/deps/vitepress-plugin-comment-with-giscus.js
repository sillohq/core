import {
  createApp,
  createCommentVNode,
  createElementBlock,
  defineComponent,
  h,
  nextTick,
  onMounted,
  openBlock,
  ref,
  watch
} from "./chunk-PAZLUHC7.js";

// node_modules/.pnpm/@giscus+vue@2.4.0_vue@3.5.24/node_modules/@giscus/vue/dist/index.mjs
var d = ["id", "host", "repo", "repoid", "category", "categoryid", "mapping", "term", "strict", "reactionsenabled", "emitmetadata", "inputposition", "theme", "lang", "loading"];
var l = defineComponent({
  __name: "Giscus",
  props: {
    id: {},
    host: {},
    repo: {},
    repoId: {},
    category: {},
    categoryId: {},
    mapping: {},
    term: {},
    theme: {},
    strict: {},
    reactionsEnabled: {},
    emitMetadata: {},
    inputPosition: {},
    lang: {},
    loading: {}
  },
  setup(s) {
    const t = ref(false);
    return onMounted(() => {
      t.value = true, import("./giscus-aTimukGI-L42GGW3Z.js");
    }), (e, m) => t.value ? (openBlock(), createElementBlock("giscus-widget", {
      key: 0,
      id: e.id,
      host: e.host,
      repo: e.repo,
      repoid: e.repoId,
      category: e.category,
      categoryid: e.categoryId,
      mapping: e.mapping,
      term: e.term,
      strict: e.strict,
      reactionsenabled: e.reactionsEnabled,
      emitmetadata: e.emitMetadata,
      inputposition: e.inputPosition,
      theme: e.theme,
      lang: e.lang,
      loading: e.loading
    }, null, 8, d)) : createCommentVNode("", true);
  }
});

// node_modules/.pnpm/vitepress-plugin-comment-with-giscus@1.1.15_vue@3.5.24/node_modules/vitepress-plugin-comment-with-giscus/lib/giscus.js
var setGiscus = (props, frontmatter, defaultEnable = true) => {
  var _a;
  const defaultProps = {
    id: "comment",
    host: "https://giscus.app",
    category: "General",
    mapping: "pathname",
    term: "Welcome to giscus!",
    reactionsEnabled: "1",
    inputPosition: "top",
    lang: "zh-CN",
    loading: "lazy",
    repo: "xxx/xxx",
    repoId: "",
    homePageShowComment: false
  };
  if (props.locales) {
    const element = document.querySelector("html");
    const lang = element.getAttribute("lang");
    if (lang && props.locales[lang]) {
      props.lang = props.locales[lang];
    }
  }
  const lightTheme = props.lightTheme || "light";
  const darkTheme = props.darkTheme || "transparent_dark";
  let oldCommentContainer = document.getElementById("giscus");
  if (oldCommentContainer) {
    oldCommentContainer.parentNode.removeChild(oldCommentContainer);
  }
  if ((frontmatter == null ? void 0 : frontmatter.value.comment) !== void 0) {
    if (!Boolean(frontmatter == null ? void 0 : frontmatter.value.comment)) {
      return;
    }
  } else {
    if (!defaultEnable) {
      return;
    }
  }
  if (!props.homePageShowComment && (!location.pathname || location.pathname === "/")) {
    return;
  }
  const isDark = ((_a = document.querySelector("html")) == null ? void 0 : _a.className.indexOf("dark")) !== -1;
  const docContent = document.getElementsByClassName("content-container")[0];
  if (docContent) {
    const bindGiscus = document.createElement("div");
    bindGiscus.setAttribute("id", "giscus");
    bindGiscus.style.height = "auto";
    bindGiscus.style.marginTop = "40px";
    bindGiscus.style.borderTop = "1px solid var(--vp-c-divider)";
    bindGiscus.style.paddingTop = "20px";
    docContent.append(bindGiscus);
    createApp({
      render: () => {
        return h(l, { ...defaultProps, theme: isDark ? darkTheme : lightTheme, ...props });
      }
    }).mount("#giscus");
  }
};
var setThemeWatch = (props) => {
  const element = document.querySelector("html");
  const lightTheme = props.lightTheme || "light";
  const darkTheme = props.darkTheme || "transparent_dark";
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type == "attributes") {
        let comment = document.getElementById("comment");
        comment == null ? void 0 : comment.setAttribute("theme", element.className.indexOf("dark") !== -1 ? darkTheme : lightTheme);
      }
    });
  });
  observer.observe(element, {
    attributeFilter: ["class"]
  });
};
var giscusTalk = (props, vitepressObj, defaultEnable = true) => {
  onMounted(() => {
    setGiscus(props, vitepressObj.frontmatter, defaultEnable);
    setThemeWatch(props);
  });
  watch(() => vitepressObj.route.path, () => nextTick(() => {
    setGiscus(props, vitepressObj.frontmatter, defaultEnable);
  }));
};
var giscus_default = giscusTalk;
export {
  giscus_default as default
};
//# sourceMappingURL=vitepress-plugin-comment-with-giscus.js.map
