"""XML-RPC exception types from the legacy stdlib transport (isinstance checks only)."""

from __future__ import annotations

import xmlrpc.client

XmlRpcFault = xmlrpc.client.Fault
XmlRpcProtocolError = xmlrpc.client.ProtocolError

__all__ = ["XmlRpcFault", "XmlRpcProtocolError"]
