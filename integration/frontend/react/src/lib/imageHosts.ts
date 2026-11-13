import { createContext, useContext } from "react";

// Which hosts' images show in comment text: the community's image_hosts, set by its admins. An image from anywhere else
// shows as a link instead, so a comment can't make its readers' browsers load something from a server its author runs
// (a tracking pixel learns each reader's IP address and when they read it). Empty, the default, means no images.
export const ImageHostsContext = createContext<readonly string[]>([]);

export const useImageHosts = () => useContext(ImageHostsContext);

/** Whether an image at this address may show: https, from exactly one of the hosts (no subdomains or lookalikes). */
export function isAllowedImage(
  src: string | undefined,
  hosts: readonly string[],
): boolean {
  if (!src || hosts.length === 0) return false;
  try {
    const url = new URL(src);
    return (
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      !url.port &&
      hosts.includes(url.hostname.toLowerCase())
    );
  } catch {
    return false;
  }
}
