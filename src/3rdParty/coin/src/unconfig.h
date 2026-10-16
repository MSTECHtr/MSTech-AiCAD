/*
 * Public Coin headers and config.h define some of the same version
 * identifiers, which can cause warnings with a lot of compilers.
 *
 * When including config.h after public Coin headers, undefine those
 * overlapping identifiers first.
 *
 * This header, like the config.h header, should not be installed on
 * the system.
 */

#ifndef COIN_INTERNAL
#error this is a private header file
#endif /* !COIN_INTERNAL */

#ifdef COIN_MAJOR_VERSION
#undef COIN_MAJOR_VERSION
#endif

#ifdef COIN_MICRO_VERSION
#undef COIN_MICRO_VERSION
#endif

#ifdef COIN_MINOR_VERSION
#undef COIN_MINOR_VERSION
#endif

#ifdef COIN_VERSION
#undef COIN_VERSION
#endif
