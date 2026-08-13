import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

/**
 * Заголовок, описание и постоянный адрес страницы.
 *
 * Портал собирается на клиенте, поэтому в разметке, отданной сервером, стоят
 * значения главной страницы и только они. У шестидесяти пяти карточек и семи
 * разделов был один заголовок на всех: в закладках, в истории браузера, в
 * выдаче поиска и в пересланной ссылке все они выглядели одинаково, а
 * различить их можно было только открыв.
 *
 * Обходчик, выполняющий код страницы, читает то, что проставит этот хук;
 * обходчик, кода не выполняющий, читает статические значения из `index.html`.
 * Оба ответа правдивы, второй просто беднее.
 *
 * Здесь же выставляется язык корневого элемента: он объявляет язык содержимого
 * и переключается вместе с выбором читателя.
 */

const SITE = "https://ragworld.org";
const SUFFIX = "RAG World";

interface Head {
  /** Заголовок страницы без имени портала: оно добавляется само. */
  title?: string;
  /** Одно предложение о странице для выдачи поиска и предпросмотра ссылки. */
  description?: string;
}

function setMeta(selector: string, attribute: string, value: string) {
  let node = document.head.querySelector<HTMLMetaElement | HTMLLinkElement>(selector);
  if (!node) {
    node = selector.startsWith("link")
      ? Object.assign(document.createElement("link"), { rel: selector.match(/rel="(.+?)"/)?.[1] })
      : Object.assign(document.createElement("meta"), {
          name: selector.match(/name="(.+?)"/)?.[1] ?? "",
        });
    if (selector.includes("property=")) {
      node.setAttribute("property", selector.match(/property="(.+?)"/)?.[1] ?? "");
    }
    document.head.appendChild(node);
  }
  node.setAttribute(attribute, value);
}

export function useDocumentHead({ title, description }: Head) {
  const { i18n } = useTranslation();
  const { pathname } = useLocation();

  useEffect(() => {
    document.documentElement.lang = i18n.language === "ru" ? "ru" : "en";

    const full = title ? `${title} — ${SUFFIX}` : SUFFIX;
    document.title = full;
    setMeta('meta[property="og:title"]', "content", full);

    if (description) {
      setMeta('meta[name="description"]', "content", description);
      setMeta('meta[property="og:description"]', "content", description);
    }

    // Постоянный адрес не несёт ни языка, ни параметров отбора: страница с
    // тем же содержимым не должна выглядеть несколькими разными.
    const url = `${SITE}${pathname}`;
    setMeta('link[rel="canonical"]', "href", url);
    setMeta('meta[property="og:url"]', "content", url);
  }, [title, description, pathname, i18n.language]);
}
