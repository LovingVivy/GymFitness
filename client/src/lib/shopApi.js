import { request } from "./api";

/** Sản phẩm đang bán — không cần đăng nhập. */
export const listProducts = () => request("/products");
