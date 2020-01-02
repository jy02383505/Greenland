# -*- coding: utf-8 -*-
import math
from limiter_upper import get_rate
from logutil import logger


def count(t):
    return len(t)


def sum(t):
    if not t:
        return 0
    sum = 0
    for v in t:
        sum = sum + v
    return sum


def sum_list_single(current_list, category):
    dev_rate = 0.0
    # logger.info("sum_list_single current_list: %s|| category: %s" % (current_list,category))
    for li in current_list:
        dev_rate = dev_rate + li[category]
    return dev_rate


def sum_list(current_list, category_list, user_list, group_list):
    all_dev_rate = []
    index = 0
    for l in current_list:
        # logger.info("sum_list category_list: %s" % category_list)
        direction_two, direction_upper = judge_direction(category_list[index])
        # logger.info("sum_list direction_two: %s|| direction_upper: %s" % (direction_two, direction_upper, ))
        if direction_two == "11":
            one_three_direction = 0.0
            two_four_direction = 0.0
            for li in category_list[index].split(","):
                if li != 'in' and li != 'out':
                    dev_ra = sum_list_single(current_list[index], li)
                    if li == 'e1' or li == 'e3':
                        one_three_direction = one_three_direction + dev_ra
                    else:
                        two_four_direction = two_four_direction + dev_ra
            if direction_upper == 'true':
                upper_rate = get_rate(user_list[index], group_list[index])
                logger.info("sum_list upper_rate: %s" % upper_rate)
                if upper_rate == None:
                    one_three_direction = one_three_direction + 0.0
                    two_four_direction = two_four_direction + 0.0
                else:
                    one_three_direction = one_three_direction + upper_rate
                    two_four_direction = two_four_direction + upper_rate
            if one_three_direction >= two_four_direction:
                all_dev_rate.append(one_three_direction)
            else:
                all_dev_rate.append(two_four_direction)
        else:
            for li in category_list[index].split(","):
                if li != 'in' and li != 'out':
                    dev_rate = sum_list_single(current_list[index], li)
                    if direction_upper == 'true':
                        upper_rate = get_rate(
                            user_list[index], group_list[index])
                        if upper_rate == None:
                            logger.info("sum_list upper_rate: %s" % upper_rate)
                            dev_rate = dev_rate + 0.0
                        else:
                            logger.info("sum_list upper_rate: %s" % upper_rate)
                            dev_rate = dev_rate + upper_rate
                    all_dev_rate.append(dev_rate)
        index = index + 1
    return all_dev_rate


def avg(t):
    return sum(t) / count(t)


def variance(t, limiter_direction=["e4"]):
    limiter_direction_variance = {}
    if not t:
        return limiter_direction_variance
    for d, r in t.items():
        if d in limiter_direction:
            avg1 = avg(r)
            sub = 0
            for v in r:
                sub = sub + math.pow((v - avg1), 2)
            limiter_direction_variance[d] = sub / count(r)
    # logger.info("variance limiter_direction_variance: %s" % limiter_direction_variance)
    return limiter_direction_variance


def judge_direction(category):
    direction_two = '00'
    direction_upper = 'false'
    # logger.info("judge_direction category: %s" % category)
    if 'e1' in category or 'e3' in category:
        direction_two = '10'
    if 'e2' in category or 'e4' in category:
        if direction_two == '10':
            direction_two = '11'
        else:
            direction_two = '01'
    if 'in' in category or 'out' in category:
        direction_upper = 'true'
    return direction_two, direction_upper


def rate_param(params_list, rate_list):
    x_ratexparam = []
    rate_list_len = len(rate_list)
    for line in range(rate_list_len):
        x_ratexparam.append(params_list[line] * rate_list[line])
    return x_ratexparam


def delete_in_out(category):

    category_list = category.split(",")
    if 'in' in category_list:
        category_list.remove('in')
    if 'out' in category_list:
        category_list.remove('out')
    return category_list
