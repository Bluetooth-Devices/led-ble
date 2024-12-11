# Changelog

<!--next-version-placeholder-->

## v1.1.1 (2024-12-11)

### Fix

* Refactor to use kwargs for construct_levels_change ([#53](https://github.com/Bluetooth-Devices/led-ble/issues/53)) ([`efd92ac`](https://github.com/Bluetooth-Devices/led-ble/commit/efd92aca9bcb05ac9d5ab72a19196c7717631552))

## v1.1.0 (2024-12-11)

### Feature

* Add Python 3.13 support ([#55](https://github.com/Bluetooth-Devices/led-ble/issues/55)) ([`05f3818`](https://github.com/Bluetooth-Devices/led-ble/commit/05f38188572e898af89f53a0bf1cc4f146186876))

## v1.0.2 (2024-06-24)

### Fix

* Fix license classifier ([#41](https://github.com/Bluetooth-Devices/led-ble/issues/41)) ([`b331b97`](https://github.com/Bluetooth-Devices/led-ble/commit/b331b9744caeb5fded22d8435bb8c5db7be8a362))

## v1.0.1 (2023-09-25)

### Fix

* Bump psr to fix CI ([#38](https://github.com/Bluetooth-Devices/led-ble/issues/38)) ([`ab09fed`](https://github.com/Bluetooth-Devices/led-ble/commit/ab09fedd632f937cb4064254c8e61c349f8c8d6d))
* Drop async_timeout on py3.11+ ([#37](https://github.com/Bluetooth-Devices/led-ble/issues/37)) ([`fba769f`](https://github.com/Bluetooth-Devices/led-ble/commit/fba769f33cf7ac1f89105e29615e3d15707ecdcf))
* Do not try to stop notify if read char is missing ([#36](https://github.com/Bluetooth-Devices/led-ble/issues/36)) ([`03c84f9`](https://github.com/Bluetooth-Devices/led-ble/commit/03c84f99deba04c3d04236f608e24ad137540b8c))

## v1.0.0 (2022-10-16)
### Feature
* Update for new bleak version ([#33](https://github.com/Bluetooth-Devices/led-ble/issues/33)) ([`2be176c`](https://github.com/Bluetooth-Devices/led-ble/commit/2be176cfc5492f35bc3fc019e385a3698ea572bb))

### Breaking
* The set_ble_device function has been renamed set_ble_device_and_advertisement_data and now requires the advertisement_data. ([`2be176c`](https://github.com/Bluetooth-Devices/led-ble/commit/2be176cfc5492f35bc3fc019e385a3698ea572bb))
* The constructor no longer takes a retry count since this does not need to be configurable ([`2be176c`](https://github.com/Bluetooth-Devices/led-ble/commit/2be176cfc5492f35bc3fc019e385a3698ea572bb))

## v0.10.1 (2022-09-15)
### Fix
* Handle additional bleak exceptions ([#31](https://github.com/Bluetooth-Devices/led-ble/issues/31)) ([`1ff94f7`](https://github.com/Bluetooth-Devices/led-ble/commit/1ff94f770e86d630892261178018d861d4e74a72))

## v0.10.0 (2022-09-13)
### Feature
* Update for bleak 0.17 support ([#29](https://github.com/Bluetooth-Devices/led-ble/issues/29)) ([`530de76`](https://github.com/Bluetooth-Devices/led-ble/commit/530de767892a51bb93a81830f418b168b3f13fd8))

## v0.9.1 (2022-09-11)
### Fix
* Typo in bleak-retry-connector min version pin ([#28](https://github.com/Bluetooth-Devices/led-ble/issues/28)) ([`8638ab8`](https://github.com/Bluetooth-Devices/led-ble/commit/8638ab86a73fae3a8407b4b6b3f9fe3c4193bfb0))

## v0.9.0 (2022-09-11)
### Feature
* Implement smart backoff via bleak-retry-connector ([#27](https://github.com/Bluetooth-Devices/led-ble/issues/27)) ([`a7bb1b1`](https://github.com/Bluetooth-Devices/led-ble/commit/a7bb1b1707c103010398091d5291d8827b730d7e))

## v0.8.5 (2022-09-11)
### Fix
* Bump bleak-retry-connector ([#26](https://github.com/Bluetooth-Devices/led-ble/issues/26)) ([`ac3823e`](https://github.com/Bluetooth-Devices/led-ble/commit/ac3823e546e7263e345b1deae8a7f0b94487a89e))

## v0.8.4 (2022-09-11)
### Fix
* Bump bleak-retry-connector ([#25](https://github.com/Bluetooth-Devices/led-ble/issues/25)) ([`0ad8e7b`](https://github.com/Bluetooth-Devices/led-ble/commit/0ad8e7bc240bcd9abfffb7efccef93186072c25c))

## v0.8.3 (2022-09-10)
### Fix
* Address property ([#24](https://github.com/Bluetooth-Devices/led-ble/issues/24)) ([`b85439f`](https://github.com/Bluetooth-Devices/led-ble/commit/b85439febb7fbcfb9fa7e41a7a6f6991bd25dff4))

## v0.8.2 (2022-09-10)
### Fix
* Bump bleak retry connector ([#23](https://github.com/Bluetooth-Devices/led-ble/issues/23)) ([`1fd8778`](https://github.com/Bluetooth-Devices/led-ble/commit/1fd8778e738b09122a15ec486bc83c7313545692))

## v0.8.1 (2022-09-10)
### Fix
* Bump bleak-retry-connector min version ([#22](https://github.com/Bluetooth-Devices/led-ble/issues/22)) ([`2112b18`](https://github.com/Bluetooth-Devices/led-ble/commit/2112b18c4a7afbb5ea04a6d8c5ddb2f8232816da))

## v0.8.0 (2022-09-10)
### Feature
* Export get_device from bleak-retry-connector ([#21](https://github.com/Bluetooth-Devices/led-ble/issues/21)) ([`5f41511`](https://github.com/Bluetooth-Devices/led-ble/commit/5f41511cd1684eb9277fc63896da63d50127b168))

## v0.7.1 (2022-09-06)
### Fix
* Effects on dream models ([#20](https://github.com/Bluetooth-Devices/led-ble/issues/20)) ([`b8126c1`](https://github.com/Bluetooth-Devices/led-ble/commit/b8126c1f5fe098efcc8c3d3a43a42ed5cc9136d8))

## v0.7.0 (2022-09-05)
### Feature
* Add newly discovered model 0x15 ([#17](https://github.com/Bluetooth-Devices/led-ble/issues/17)) ([`3c5f15c`](https://github.com/Bluetooth-Devices/led-ble/commit/3c5f15c80520b76fe6fa9e0933f64c3419cd3b07))

## v0.6.0 (2022-09-04)
### Feature
* Add support for more protocols ([#16](https://github.com/Bluetooth-Devices/led-ble/issues/16)) ([`c7bbb15`](https://github.com/Bluetooth-Devices/led-ble/commit/c7bbb15ec2dd291f5918850b3bdddec8cf1abae6))

## v0.5.4 (2022-08-29)
### Fix
* W channel not being cleared on rgb set ([#15](https://github.com/Bluetooth-Devices/led-ble/issues/15)) ([`048bdff`](https://github.com/Bluetooth-Devices/led-ble/commit/048bdffd52ea78ba66a1d33793db58a725bc894b))

## v0.5.3 (2022-08-29)
### Fix
* Brightness ([#14](https://github.com/Bluetooth-Devices/led-ble/issues/14)) ([`01dcf7b`](https://github.com/Bluetooth-Devices/led-ble/commit/01dcf7bd5f92a0c487924211490ba0498708100d))

## v0.5.2 (2022-08-29)
### Fix
* Missing exports ([#13](https://github.com/Bluetooth-Devices/led-ble/issues/13)) ([`911c2a0`](https://github.com/Bluetooth-Devices/led-ble/commit/911c2a0dcbdc4041247fe53a060ae4a50a85faa7))

## v0.5.1 (2022-08-29)
### Fix
* Cleanups ([#12](https://github.com/Bluetooth-Devices/led-ble/issues/12)) ([`9d3ae2a`](https://github.com/Bluetooth-Devices/led-ble/commit/9d3ae2a80bfc9d17bc9603003852b010a56a2494))

## v0.5.0 (2022-08-29)
### Feature
* Add rgbw support ([#11](https://github.com/Bluetooth-Devices/led-ble/issues/11)) ([`14ae97b`](https://github.com/Bluetooth-Devices/led-ble/commit/14ae97ba4b51fb7ebb81634028e1eac623e9a3f5))

## v0.4.2 (2022-08-29)
### Fix
* Add log ([#10](https://github.com/Bluetooth-Devices/led-ble/issues/10)) ([`d95fc61`](https://github.com/Bluetooth-Devices/led-ble/commit/d95fc61d0745002709558bc05812e8b5589ada62))

## v0.4.1 (2022-08-29)
### Fix
* Add state to log ([#9](https://github.com/Bluetooth-Devices/led-ble/issues/9)) ([`ee85bdd`](https://github.com/Bluetooth-Devices/led-ble/commit/ee85bddec3b5dac4de1aa38742662ccf97fc0fda))

## v0.4.0 (2022-08-29)
### Feature
* Add model data ([#8](https://github.com/Bluetooth-Devices/led-ble/issues/8)) ([`6df04cf`](https://github.com/Bluetooth-Devices/led-ble/commit/6df04cf9d0dfeaf6836830634df8df1a2bcbeb95))

## v0.3.0 (2022-08-29)
### Feature
* Add white channel ([#7](https://github.com/Bluetooth-Devices/led-ble/issues/7)) ([`3112249`](https://github.com/Bluetooth-Devices/led-ble/commit/31122499beb71f7af68ad5854fb58f112803c654))

## v0.2.2 (2022-08-29)
### Fix
* Remove scaling ([#6](https://github.com/Bluetooth-Devices/led-ble/issues/6)) ([`89ac78e`](https://github.com/Bluetooth-Devices/led-ble/commit/89ac78e5e41e4c5123cb8ef39505ca6bb9c5e24e))

## v0.2.1 (2022-08-29)
### Fix
* Fix disconnect ([#5](https://github.com/Bluetooth-Devices/led-ble/issues/5)) ([`44f79ee`](https://github.com/Bluetooth-Devices/led-ble/commit/44f79eea35fb027299cda5b6c3fa06da9572f258))

## v0.2.0 (2022-08-29)
### Feature
* Add example ([#4](https://github.com/Bluetooth-Devices/led-ble/issues/4)) ([`9d25f2a`](https://github.com/Bluetooth-Devices/led-ble/commit/9d25f2a2fd1043cf4679215ce16c0888f9ed6fa8))

## v0.1.0 (2022-08-29)
### Feature
* First release ([#3](https://github.com/Bluetooth-Devices/led-ble/issues/3)) ([`0875dc4`](https://github.com/Bluetooth-Devices/led-ble/commit/0875dc4ca17960cb634b66c3a3c61f9ff2c5f490))
* Build out the class ([#2](https://github.com/Bluetooth-Devices/led-ble/issues/2)) ([`f70c1a3`](https://github.com/Bluetooth-Devices/led-ble/commit/f70c1a3288dfcf749200cab167f1ee67b2ffcd3e))

### Fix
* Ci ([#1](https://github.com/Bluetooth-Devices/led-ble/issues/1)) ([`dba3484`](https://github.com/Bluetooth-Devices/led-ble/commit/dba3484f8aabb76db51365179cfecfb1caeed528))
