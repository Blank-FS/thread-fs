import { createContext, useContext } from "react";

// Which hosts' images show in comment text: the community's image_hosts, set by its admins. An image from anywhere else
// shows as a link instead, so a comment can't make its readers' browsers load something from a server its author runs
// (a tracking pixel learns each reader's IP address and when they read it). Empty, the default, means no images.
// "any" shows every image, for text moderated elsewhere that a host renders with ThreadFSMarkdown; never for comments.
export type ImageHosts = readonly string[] | "any";

export const ImageHostsContext = createContext<ImageHosts>([]);

export const useImageHosts = () => useContext(ImageHostsContext);

/** Whether an image at this address may show: https, from exactly one of the hosts (no subdomains or lookalikes), or any
 * http(s) address with "any". */
export function isAllowedImage(
  src: string | undefined,
  hosts: ImageHosts,
): boolean {
  if (!src || hosts.length === 0) return false;
  try {
    const url = new URL(src);
    if (hosts === "any")
      return (
        (url.protocol === "https:" || url.protocol === "http:") &&
        !url.username &&
        !url.password
      );
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
